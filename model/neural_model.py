"""
PyTorch 신경망 모델
RTX 5070 Ti CUDA 12.x 최적화
Residual MLP + Batch Normalization
"""
import logging
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODEL_DIR, RANDOM_STATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

torch.manual_seed(RANDOM_STATE)


class ResidualBlock(nn.Module):
    def __init__(self, dim: int, dropout: float = 0.2):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
        )
        self.activation = nn.GELU()

    def forward(self, x):
        return self.activation(x + self.block(x))


class KBOPredictor(nn.Module):
    """KBO 승패 예측 신경망 (Residual MLP)"""

    def __init__(self, input_dim: int, hidden_dims: list[int] = None, dropout: float = 0.3):
        super().__init__()

        if hidden_dims is None:
            hidden_dims = [256, 256, 128, 128, 64]

        layers = []

        # 입력층
        layers.append(nn.Linear(input_dim, hidden_dims[0]))
        layers.append(nn.BatchNorm1d(hidden_dims[0]))
        layers.append(nn.GELU())
        layers.append(nn.Dropout(dropout))

        # Residual 블록 (같은 크기)
        current_dim = hidden_dims[0]
        for next_dim in hidden_dims[1:]:
            if next_dim == current_dim:
                layers.append(ResidualBlock(current_dim, dropout))
            else:
                layers.append(nn.Linear(current_dim, next_dim))
                layers.append(nn.BatchNorm1d(next_dim))
                layers.append(nn.GELU())
                layers.append(nn.Dropout(dropout * 0.5))
                current_dim = next_dim

        self.backbone = nn.Sequential(*layers)

        # 출력층 (Sigmoid 제거 - BCEWithLogitsLoss 사용)
        self.head = nn.Sequential(
            nn.Linear(current_dim, 32),
            nn.GELU(),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        features = self.backbone(x)
        return self.head(features).squeeze(-1)


def get_device() -> torch.device:
    """최적 디바이스 선택 (RTX 5070 Ti 우선)"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"GPU 사용: {gpu_name}")
        # RTX 5070 Ti는 SM 아키텍처 최적화
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False
        return device
    else:
        logger.warning("CUDA 없음 - CPU 사용")
        return torch.device("cpu")


class EarlyStopping:
    def __init__(self, patience: int = 15, min_delta: float = 1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.best_loss = float("inf")
        self.counter = 0
        self.best_state = None

    def __call__(self, val_loss: float, model: nn.Module) -> bool:
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
            self.best_state = {k: v.clone() for k, v in model.state_dict().items()}
            return False
        else:
            self.counter += 1
            return self.counter >= self.patience


def train_neural_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 300,
    batch_size: int = 512,
    lr: float = 1e-3,
) -> tuple[KBOPredictor, StandardScaler]:
    """PyTorch 신경망 학습"""

    device = get_device()

    # 정규화
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train).astype(np.float32)
    X_val_scaled = scaler.transform(X_val).astype(np.float32)

    # 텐서 변환
    X_tr_t = torch.FloatTensor(X_train_scaled).to(device)
    y_tr_t = torch.FloatTensor(y_train).to(device)
    X_va_t = torch.FloatTensor(X_val_scaled).to(device)
    y_va_t = torch.FloatTensor(y_val).to(device)

    train_dataset = TensorDataset(X_tr_t, y_tr_t)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=False,
    )

    input_dim = X_train_scaled.shape[1]
    model = KBOPredictor(input_dim=input_dim).to(device)

    # AMP (Automatic Mixed Precision) - RTX 5070 Ti 최적화
    use_amp = device.type == "cuda"
    scaler_amp = torch.amp.GradScaler("cuda") if use_amp else None

    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    criterion = nn.BCEWithLogitsLoss()

    early_stopping = EarlyStopping(patience=20)

    logger.info(f"신경망 학습 시작 (device={device}, epochs={epochs}, batch={batch_size})")
    logger.info(f"모델 파라미터: {sum(p.numel() for p in model.parameters()):,}")

    best_val_auc = 0.0

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0

        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()

            if use_amp:
                with torch.amp.autocast("cuda"):
                    pred = model(X_batch)
                    loss = criterion(pred, y_batch)
                scaler_amp.scale(loss).backward()
                scaler_amp.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler_amp.step(optimizer)
                scaler_amp.update()
            else:
                pred = model(X_batch)
                loss = criterion(pred, y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            train_loss += loss.item()

        scheduler.step()

        # 검증
        model.eval()
        with torch.no_grad():
            if use_amp:
                with torch.amp.autocast("cuda"):
                    val_logits = model(X_va_t)
            else:
                val_logits = model(X_va_t)
            val_loss = criterion(val_logits, y_va_t).item()
            val_prob = torch.sigmoid(val_logits).cpu().numpy()

        from sklearn.metrics import roc_auc_score
        try:
            val_auc = roc_auc_score(y_val, val_prob)
        except Exception:
            val_auc = 0.5

        if val_auc > best_val_auc:
            best_val_auc = val_auc

        if (epoch + 1) % 20 == 0:
            avg_train_loss = train_loss / len(train_loader)
            logger.info(
                f"Epoch {epoch+1:3d}/{epochs} | "
                f"Train Loss: {avg_train_loss:.4f} | "
                f"Val Loss: {val_loss:.4f} | "
                f"Val AUC: {val_auc:.4f}"
            )

        if early_stopping(val_loss, model):
            logger.info(f"Early stopping at epoch {epoch+1}")
            break

    # 최적 가중치 복원
    if early_stopping.best_state:
        model.load_state_dict(early_stopping.best_state)

    logger.info(f"신경망 학습 완료 | Best Val AUC: {best_val_auc:.4f}")
    return model.cpu(), scaler


def save_neural_model(model: KBOPredictor, scaler: StandardScaler):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_DIR / "neural_model.pt")
    joblib.dump(scaler, MODEL_DIR / "neural_scaler.pkl")
    # 모델 구조 저장
    model_config = {
        "input_dim": model.backbone[0].in_features,
    }
    joblib.dump(model_config, MODEL_DIR / "neural_config.pkl")
    logger.info(f"신경망 모델 저장 완료: {MODEL_DIR}")


def load_neural_model() -> tuple[KBOPredictor, StandardScaler]:
    config = joblib.load(MODEL_DIR / "neural_config.pkl")
    scaler = joblib.load(MODEL_DIR / "neural_scaler.pkl")
    model = KBOPredictor(input_dim=config["input_dim"])
    model.load_state_dict(torch.load(MODEL_DIR / "neural_model.pt", map_location="cpu"))
    model.eval()
    return model, scaler


def predict_neural(model: KBOPredictor, scaler: StandardScaler,
                   X: np.ndarray, device: torch.device = None) -> np.ndarray:
    if device is None:
        device = get_device()

    model = model.to(device)
    model.eval()

    X_scaled = scaler.transform(X).astype(np.float32)
    X_t = torch.FloatTensor(X_scaled).to(device)

    with torch.no_grad():
        logits = model(X_t)
        probs = torch.sigmoid(logits).cpu().numpy()

    return probs
