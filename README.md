[README.md](https://github.com/user-attachments/files/29487445/README.md)
🛡️ Industrial AI Gate & Dynamic PPE Verification System

An enterprise-grade, edge-computing based Proof-of-Concept (PoC) for industrial safety and access control. This system seamlessly integrates QR-based attendance, dynamic Role-Based Access Control (RBAC), and real-time YOLOv8 AI computer vision to enforce Personal Protective Equipment (PPE) compliance.

Built specifically for Small and Medium-sized Enterprises (SMEs), it provides a low Total Cost of Ownership (TCO) solution with a robust Human-AI Mutual Supervision workflow.

💡 Core Philosophy: Human-AI Mutual Supervision

Traditional "Unmanned" AI safety systems are often too expensive for SMEs and vulnerable to edge cases (e.g., a worker holding a helmet instead of wearing it). This system pioneers a highly pragmatic "1 Guard + 1 AI Camera" dual-track mutual supervision model:

Humans back up AI: The physical presence of a security guard deters cheating and handles hardware anomalies (e.g., USB camera disconnection).

AI audits Humans: Every gate entry triggers an immutable database record and snapshot. Even if a guard manually "approves" a worker without proper PPE due to favoritism, the AI's original FAIL assessment and the watermarked evidence photo will be logged in the monthly CSV audit trail for executive review.

🏗️ System Architecture

The system adopts a decoupled architecture, using a lightweight SQLite database as the unified data bus.

qr_code.py (HR & Admin Portal): Manages worker RBAC profiles, generates QR IDs, and handles batch onboarding.

gate1_attendance.py (Gate 1): Utilizes PyZbar for seamless, non-stop QR attendance capture with automated camera warm-up logic.

gate2_ppe_system.py (Gate 2): Performs dynamic YOLOv8 inference based on the worker's role-assigned PPE requirements. Includes a PIN-protected admin override feature.

⚖️ Pros & Cons Analysis

✅ Pros (Strengths)

Human-AI Mutual Supervision: Acts as a fail-safe, preventing AI "hallucination" or guard negligence.

Low Latency Edge Execution: Runs locally via launchd, eliminating reliance on cloud APIs—ideal for factory floors with poor internet.

Rapid Deployment: Built with Streamlit for fast iteration and an intuitive dashboard experience.

Audit Trail Accountability: The dual-snapshot system (raw + audited) creates an irrefutable compliance record for safety certifications.

⚠️ Cons (Limitations)

Hardware Dependence: Standard webcams can struggle in extreme industrial environments (dust/low light).

SQLite Single-Writer Limit: Not suitable for high-throughput shifts with hundreds of simultaneous workers; requires migration to PostgreSQL for scale.

Manual Model Retraining: Does not support real-time "online learning"; captured images must be manually processed for model retraining.

Security Surface: QR-based auth is vulnerable to "credential sharing"; lacks biometric validation.

🚀 Tech Stack

Frontend/State: Streamlit

Vision: OpenCV

AI Engine: YOLOv8 (Custom-trained)

Decoding: PyZbar

Data Bus: SQLite3

Deployment: macOS launchd

Real-time Alert System: Integrates with Telegram Bot API to dispatch instant notifications and annotated violation photos directly to supervisors' mobile devices.

Audio Feedback: Utilizes a custom sound_manager to provide clear, localized acoustic cues (granted, denied, alerts) to workers during the fast-paced scan process.

🛠️ Quick Start

1. Prerequisites

pip install streamlit opencv-python pyzbar ultralytics pandas qrcode requests


Ensure your best.pt weights file is in the root directory.

2. Launch the Cluster

# Make the cluster script executable
chmod +x setup_ppe_cluster.sh

# Deploy as background daemons
./setup_ppe_cluster.sh


Local Access:

👨‍💼 HR Portal: http://localhost:8501

⏱️ Gate 1: http://localhost:8502

🛡️ Gate 2: http://localhost:8503

🗺️ Evolution Path

To scale this PoC for a large-scale production environment:

Concurrency: Migrate from SQLite to PostgreSQL with connection pooling.

Architecture: Move from Streamlit to a FastAPI + React/Vue stack to eliminate memory leaks.

Storage: Integrate AWS S3 / MinIO for distributed image management.

AI Precision: Upgrade to YOLO-Pose to calculate spatial topology (e.g., verifying if the helmet is on the head, not just in the frame).

Built with passion for industrial safety and AI pragmatism.
