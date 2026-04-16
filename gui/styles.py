DIGITAL_ASSIGNED = """
    background-color: #d4edda;
    color: #155724;
"""

NOT_ASSIGNED = """
    background-color: #f8f9fa;
    color: #212529;
"""

MANUALLY_EXCLUDED = """
    background-color: #f8d7da;
    color: #721c24;
"""

MANUALLY_ASSIGNED = """
    background-color: #fff3cd;
    color: #856404;
"""

TABLE_HEADER_STYLE = """
    QHeaderView::section {
        background-color: #4a5568;
        color: white;
        padding: 8px;
        border: 1px solid #2d3748;
        font-weight: bold;
    }
"""

BUTTON_PRIMARY_STYLE = """
    QPushButton {
        background-color: #4299e1;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-size: 13px;
    }
    QPushButton:hover {
        background-color: #3182ce;
    }
    QPushButton:pressed {
        background-color: #2b6cb0;
    }
    QPushButton:disabled {
        background-color: #cbd5e0;
        color: #718096;
    }
"""

BUTTON_SECONDARY_STYLE = """
    QPushButton {
        background-color: #718096;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: #4a5568;
    }
    QPushButton:pressed {
        background-color: #2d3748;
    }
    QPushButton:disabled {
        background-color: #cbd5e0;
        color: #718096;
    }
"""

INPUT_STYLE = """
    QLineEdit, QComboBox, QSpinBox {
        padding: 6px;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
        border-color: #4299e1;
    }
"""

LABEL_STYLE = """
    QLabel {
        font-size: 13px;
        color: #2d3748;
    }
"""

CARD_STYLE = """
    QFrame {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 10px;
    }
"""
