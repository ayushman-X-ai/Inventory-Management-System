import sys
import sqlite3
import hashlib
from datetime import datetime, timedelta
import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import json
 
# Database Manager
class DatabaseManager:
    def __init__(self, db_name="inventory.db"):
        self.db_name = db_name
        self.init_database()
     
    def init_database(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
         
        # Users table
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
         
        # Categories table
        cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT)''')
         
        # Items table
        cursor.execute('''CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER, quantity INTEGER,
            price REAL, min_stock INTEGER, supplier TEXT, date_added TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id))''')
         
        # Add default admin user
        cursor.execute("INSERT OR IGNORE INTO users VALUES (1, 'admin', ?, 'admin')", 
                      (hashlib.sha256('admin'.encode()).hexdigest(),))
         
        conn.commit()
        conn.close()
    def execute_query(self, query, params=(), fetch=False):
        conn = None
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall() if fetch else None
            conn.commit()
            return result
        except Exception as e:
            print(f"Database error: {e}")
            return None
        finally:
            if conn:
                conn.close()  # Always close connection
 
# Login Dialog
class LoginDialog(QDialog):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.user_role = None
        self.setup_ui()
     
    def setup_ui(self):
        self.setWindowTitle("Inventory Management - Login")
        self.setFixedSize(400, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel#title {
                font-size: 28px;
                font-weight: bold;
                color: #333;
                margin-bottom: 20px;
            }
            QLineEdit {
                padding: 12px;
                border: 1px solid #ccc;
                border-radius: 5px;
                font-size: 14px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #2196F3;
            }
            QPushButton {
                padding: 12px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QLabel#error_label {
                color: red;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignCenter)

        # Title
        title = QLabel("INVENTORY MANAGER")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)

        # Form
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(15)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)

        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.login)

        form_layout.addWidget(self.username)
        form_layout.addWidget(self.password)
        form_layout.addWidget(login_btn)

        layout.addWidget(title)
        layout.addWidget(form_widget)
        layout.addStretch()
     
    def login(self):
        username = self.username.text()
        password = hashlib.sha256(self.password.text().encode()).hexdigest()
         
        result = self.db_manager.execute_query(
            "SELECT role FROM users WHERE username=? AND password=?", 
            (username, password), fetch=True)
         
        if result:
            self.user_role = result[0][0]
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid credentials!")
 
# Chart Widget
class ChartWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(7, 5), facecolor='white')
        super().__init__(self.figure)
        self.setParent(parent)
        self.ax = None
        self.bars = None
        self.annot = None
        self.anim = None # To keep a reference to the animation
        self.mpl_connect('motion_notify_event', self.hover)

    def plot_stock_levels(self, data):
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)

        if not data:
            self.ax.text(0.5, 0.5, 'No data to display', ha='center', va='center')
            self.draw()
            return

        items, quantities = zip(*data)
        colors = ['#f44336' if q < 10 else '#ff9800' if q < 20 else '#4CAF50' for q in quantities]

        # Initial plot with heights of 0 for animation
        self.bars = self.ax.bar(range(len(items)), [0] * len(quantities), color=colors)
        
        self.ax.set_xticks(range(len(items)))
        self.ax.set_xticklabels(items, rotation=45, ha='right', fontsize=10)
        self.ax.set_ylabel('Quantity', fontsize=12)
        self.ax.set_title('Top 10 Stock Levels', fontsize=14, fontweight='bold')
        upper_limit = max(quantities) * 1.15 if quantities else 10
        if upper_limit == 0:
            upper_limit = 10
        self.ax.set_ylim(0, upper_limit)
        
        # Style the plot
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.tick_params(axis='x', length=0)
        self.ax.grid(axis='y', linestyle='--', alpha=0.7)

        # Annotation for hover effect
        self.annot = self.ax.annotate("", xy=(0,0), xytext=(-20,20), textcoords="offset points",
                                       bbox=dict(boxstyle="round", fc="w", ec="k", lw=1),
                                       arrowprops=dict(arrowstyle="->"))
        self.annot.set_visible(False)

        self.figure.tight_layout(pad=2.0)

        def animate(frame):
            for i, bar in enumerate(self.bars):
                target_height = quantities[i]
                # Simple easing function
                progress = frame / 100.0
                ease_progress = progress * progress # ease-in
                current_height = target_height * ease_progress
                bar.set_height(current_height)
            return self.bars

        # Create and store the animation
        self.anim = FuncAnimation(self.figure, animate, frames=100, interval=15, blit=False, repeat=False)

        self.draw()

    def hover(self, event):
        if not self.ax or not self.bars:
            return
            
        vis = self.annot.get_visible()
        if event.inaxes == self.ax:
            for bar in self.bars:
                cont, ind = bar.contains(event)
                if cont:
                    self.update_annot(bar)
                    self.annot.set_visible(True)
                    self.figure.canvas.draw_idle()
                    return
        
        if vis:
            self.annot.set_visible(False)
            self.figure.canvas.draw_idle()

    def update_annot(self, bar):
        x = bar.get_x() + bar.get_width() / 2.
        y = bar.get_height()
        self.annot.xy = (x, y)
        text = f"Qty: {int(y)}"
        self.annot.set_text(text)
        self.annot.get_bbox_patch().set_alpha(0.7)
 
# Main Application
class InventoryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.current_user_role = None
        self.dark_theme = False
        self.apply_theme()
        self.setup_ui()
         
    def setup_ui(self):
        self.setWindowTitle("Advanced Inventory Management System")
        self.setGeometry(100, 100, 1200, 800)
         
        # Login first
        login_dialog = LoginDialog(self.db_manager)
        if login_dialog.exec_() == QDialog.Accepted:
            self.current_user_role = login_dialog.user_role
        else:
            sys.exit()
         
        # Central widget with tabs
        central_widget = QTabWidget()
        self.setCentralWidget(central_widget)
         
        # Dashboard tab
        self.dashboard_widget = self.create_dashboard()
        central_widget.addTab(self.dashboard_widget, "Dashboard")
         
        # Items management tab
        self.items_widget = self.create_items_tab()
        central_widget.addTab(self.items_widget, "Items")
         
        # Categories tab
        self.categories_widget = self.create_categories_tab()
        central_widget.addTab(self.categories_widget, "Categories")
         
        # Reports tab
        self.reports_widget = self.create_reports_tab()
        central_widget.addTab(self.reports_widget, "Reports")
         
        # Toolbar
        self.create_toolbar()
         
        # Status bar
        self.statusBar().showMessage("Ready")
         
        # Load initial data
        self.load_categories()

    def apply_theme(self):
        app = QApplication.instance()
        if self.dark_theme:
            app.setStyleSheet("""
                QWidget { background-color: #2d2d2d; color: #f5f5f5; font-family: 'Segoe UI'; }
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit { 
                    padding: 8px; border: 2px solid #555; border-radius: 5px; 
                    background-color: #3d3d3d; color: #f5f5f5; font-size: 14px; }
                QLineEdit:focus, QComboBox:focus { border-color: #4CAF50; }
                QPushButton { 
                    padding: 10px 20px; background-color: #4CAF50; color: white; 
                    border: none; border-radius: 5px; font-size: 14px; font-weight: bold; }
                QPushButton:hover { background-color: #45a049; }
                QPushButton:pressed { background-color: #3d8b40; }
                QTableWidget { 
                    gridline-color: #555; background-color: #3d3d3d; 
                    alternate-background-color: #4d4d4d; color: #f5f5f5; }
                QTableWidget::item { padding: 8px; }
                QTableWidget::item:selected { background-color: #4CAF50; color: white; }
                QHeaderView::section { 
                    background-color: #2196F3; color: white; padding: 10px; 
                    font-weight: bold; border: none; }
                QTabWidget::pane { border: 1px solid #555; background-color: #3d3d3d; border-top-right-radius: 8px; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;}
                QTabWidget > QTabBar {
                    alignment: center;
                }
                QTabBar::tab { 
                    background-color: #3d3d3d;
                    color: #f5f5f5;
                    padding: 12px 25px;
                    border: 1px solid #555;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    margin: 0 4px;
                }
                QTabBar::tab:hover {
                    background-color: #4d4d4d;
                }
                QTabBar::tab:selected { 
                    background-color: #4CAF50; 
                    color: white; 
                    border-bottom-color: #3d3d3d;
                }
                QGroupBox { 
                    font-weight: bold; border: 1px solid #555; border-radius: 10px; 
                    margin-top: 10px; padding: 10px; color: #f5f5f5; 
                    background-color: #3d3d3d;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px;
                }
                QFrame {
                    border-radius: 15px;
                }
                QLabel { color: #f5f5f5; }
                QListWidget { background-color: #3d3d3d; color: #f5f5f5; }
                QDialog { background-color: #2d2d2d; }
            """)
        else:
            app.setStyleSheet("""
                QWidget { background-color: #f5f5f5; font-family: 'Segoe UI'; }
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit { 
                    padding: 8px; border: 2px solid #ddd; border-radius: 5px; 
                    background-color: white; font-size: 14px; }
                QLineEdit:focus, QComboBox:focus { border-color: #4CAF50; }
                QPushButton { 
                    padding: 10px 20px; background-color: #4CAF50; color: white; 
                    border: none; border-radius: 5px; font-size: 14px; font-weight: bold; }
                QPushButton:hover { background-color: #45a049; }
                QPushButton:pressed { background-color: #3d8b40; }
                QTableWidget { 
                    gridline-color: #ddd; background-color: white; 
                    alternate-background-color: #f9f9f9; }
                QTableWidget::item { padding: 8px; }
                QTableWidget::item:selected { background-color: #4CAF50; color: white; }
                QHeaderView::section { 
                    background-color: #2196F3; color: white; padding: 10px; 
                    font-weight: bold; border: none; }
                QTabWidget::pane { border: 1px solid #ddd; background-color: white; border-top-right-radius: 8px; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;}
                QTabWidget > QTabBar {
                    alignment: center;
                }
                QTabBar::tab { 
                    background-color: #e0e0e0; 
                    color: #333;
                    padding: 12px 25px;
                    border: 1px solid #ddd;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    margin: 0 4px;
                }
                QTabBar::tab:hover {
                    background-color: #f0f0f0;
                }
                QTabBar::tab:selected { 
                    background-color: #4CAF50; 
                    color: white; 
                    border-bottom-color: #ffffff;
                }
                QGroupBox { 
                    font-weight: bold; border: 1px solid #ddd; border-radius: 10px; 
                    margin-top: 10px; padding: 10px;
                    background-color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px;
                }
                QFrame {
                    border-radius: 15px;
                }
            """)

    def toggle_theme(self):
        self.dark_theme = not self.dark_theme
        self.apply_theme()
     
    def create_toolbar(self):
        """Create application toolbar"""
        toolbar = self.addToolBar("Main")
         
        # Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_all_data)
        toolbar.addAction(refresh_action)
         
        toolbar.addSeparator()
         
        # Export actions
        export_excel_action = QAction("Export Excel", self)
        export_excel_action.triggered.connect(self.export_to_excel)
        toolbar.addAction(export_excel_action)
         
        export_pdf_action = QAction("Export PDF", self)
        export_pdf_action.triggered.connect(self.export_to_pdf)
        toolbar.addAction(export_pdf_action)
         
        toolbar.addSeparator()
         
        # Logout action
        logout_action = QAction("Logout", self)
        logout_action.triggered.connect(self.logout)
        toolbar.addAction(logout_action)

        # Spacer to push items to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # Theme toggle button
        theme_action = QAction("Toggle Theme", self)
        theme_action.triggered.connect(self.toggle_theme)
        toolbar.addAction(theme_action)

     
    def create_dashboard(self):
        """Create an interactive bento-grid dashboard"""
        widget = QWidget()
        layout = QGridLayout()
        layout.setSpacing(20)

        # Fetch data
        total_items = len(self.db_manager.execute_query("SELECT * FROM items", fetch=True) or [])
        low_stock_items = self.db_manager.execute_query(
            "SELECT name, quantity FROM items WHERE quantity <= min_stock", fetch=True) or []
        low_stock_count = len(low_stock_items)
        total_categories = len(self.db_manager.execute_query("SELECT * FROM categories", fetch=True) or [])
        recent_items = self.db_manager.execute_query(
            "SELECT name, date_added FROM items ORDER BY date_added DESC LIMIT 5", fetch=True) or []

        # --- Bento Grid Items ---

        # 1. Total Items Card (Large)
        total_card = self.create_stat_card("Total Items", str(total_items), "#2196F3", "📦")
        layout.addWidget(total_card, 0, 0, 2, 2)  # Spans 2 rows, 2 columns

        # 2. Low Stock Card
        low_stock_card = self.create_stat_card("Low Stock", str(low_stock_count), "#f44336", "⚠️")
        layout.addWidget(low_stock_card, 0, 2, 1, 1)

        # 3. Categories Card
        categories_card = self.create_stat_card("Categories", str(total_categories), "#4CAF50", "🏷️")
        layout.addWidget(categories_card, 1, 2, 1, 1)

        # 4. Stock Level Chart (Large)
        self.chart_widget = ChartWidget()
        items_data = self.db_manager.execute_query(
            "SELECT name, quantity FROM items ORDER BY quantity DESC LIMIT 10", fetch=True)
        if items_data:
            self.chart_widget.plot_stock_levels(items_data)
        chart_container = QGroupBox("Stock Levels")
        chart_layout = QVBoxLayout()
        chart_layout.addWidget(self.chart_widget)
        chart_container.setLayout(chart_layout)
        layout.addWidget(chart_container, 2, 0, 2, 3)

        # 5. Low Stock Items List
        low_stock_list = QListWidget()
        if low_stock_items:
            for name, qty in low_stock_items:
                low_stock_list.addItem(f"{name} (Qty: {qty})")
        else:
            low_stock_list.addItem("No low stock items.")
        low_stock_group = QGroupBox("Low Stock Items")
        low_stock_layout = QVBoxLayout()
        low_stock_layout.addWidget(low_stock_list)
        low_stock_group.setLayout(low_stock_layout)
        layout.addWidget(low_stock_group, 0, 3, 2, 1)

        # 6. Recently Added Items
        recent_items_list = QListWidget()
        if recent_items:
            for name, date_added in recent_items:
                recent_items_list.addItem(f"{name} ({date_added.split(' ')[0]})")
        else:
            recent_items_list.addItem("No recent items.")
        recent_items_group = QGroupBox("Recently Added")
        recent_items_layout = QVBoxLayout()
        recent_items_layout.addWidget(recent_items_list)
        recent_items_group.setLayout(recent_items_layout)
        layout.addWidget(recent_items_group, 2, 3, 2, 1)

        widget.setLayout(layout)
        return widget
     
    def create_stat_card(self, title, value, color, icon):
        """Create a modern, interactive statistics card"""
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setFrameShadow(QFrame.Raised)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 15px;
                padding: 10px;
            }}
        """)

        layout = QHBoxLayout()
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 48px; color: white;")
        
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(10, 0, 0, 0)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 36px; font-weight: bold; color: white;")
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; color: white;")
        
        text_layout.addWidget(value_label)
        text_layout.addWidget(title_label)
        text_layout.addStretch()

        layout.addWidget(icon_label)
        layout.addLayout(text_layout)
        layout.addStretch()
        
        card.setLayout(layout)
        return card
     
    def create_items_tab(self):
        """Create items management tab"""
        widget = QWidget()
        layout = QVBoxLayout()
         
        # Search and filter
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search items...")
        self.search_input.textChanged.connect(self.filter_items)
         
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.currentTextChanged.connect(self.filter_items)
         
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(QLabel("Category:"))
        search_layout.addWidget(self.category_filter)
         
        # Items table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(8)
        self.items_table.setHorizontalHeaderLabels([
            "ID", "Name", "Category", "Quantity", "Price", "Min Stock", "Supplier", "Date Added"
        ])
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setAlternatingRowColors(True)
         
        # Item form
        form_group = QGroupBox("Add/Edit Item")
        form_layout = QFormLayout()
         
        self.item_name = QLineEdit()
        self.item_category = QComboBox()
        self.item_quantity = QSpinBox()
        self.item_quantity.setRange(0, 999999)
        self.item_price = QDoubleSpinBox()
        self.item_price.setRange(0, 999999.99)
        self.item_price.setDecimals(2)
        self.item_min_stock = QSpinBox()
        self.item_min_stock.setRange(0, 999999)
        self.item_supplier = QLineEdit()
         
        form_layout.addRow("Name:", self.item_name)
        form_layout.addRow("Category:", self.item_category)
        form_layout.addRow("Quantity:", self.item_quantity)
        form_layout.addRow("Price:", self.item_price)
        form_layout.addRow("Min Stock:", self.item_min_stock)
        form_layout.addRow("Supplier:", self.item_supplier)
         
        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Item")
        add_btn.clicked.connect(self.add_item)
        update_btn = QPushButton("Update Item")
        update_btn.clicked.connect(self.update_item)
        delete_btn = QPushButton("Delete Item")
        delete_btn.clicked.connect(self.delete_item)
        delete_btn.setStyleSheet("QPushButton { background-color: #f44336; }")
         
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(update_btn)
        btn_layout.addWidget(delete_btn)
         
        form_layout.addRow(btn_layout)
        form_group.setLayout(form_layout)
         
        layout.addLayout(search_layout)
        layout.addWidget(self.items_table)
        layout.addWidget(form_group)
         
        widget.setLayout(layout)
        return widget
     
    def create_categories_tab(self):
        """Create categories management tab"""
        widget = QWidget()
        layout = QHBoxLayout()
         
        # Categories list
        self.categories_list = QListWidget()
        self.categories_list.itemClicked.connect(self.load_category_details)
         
        # Category form
        form_group = QGroupBox("Add/Edit Category")
        form_layout = QFormLayout()
         
        self.category_name = QLineEdit()
        self.category_description = QTextEdit()
        self.category_description.setMaximumHeight(100)
         
        form_layout.addRow("Name:", self.category_name)
        form_layout.addRow("Description:", self.category_description)
         
        # Buttons
        btn_layout = QHBoxLayout()
        add_cat_btn = QPushButton("Add Category")
        add_cat_btn.clicked.connect(self.add_category)
        update_cat_btn = QPushButton("Update Category")
        update_cat_btn.clicked.connect(self.update_category)
        delete_cat_btn = QPushButton("Delete Category")
        delete_cat_btn.clicked.connect(self.delete_category)
        delete_cat_btn.setStyleSheet("QPushButton { background-color: #f44336; }")
         
        btn_layout.addWidget(add_cat_btn)
        btn_layout.addWidget(update_cat_btn)
        btn_layout.addWidget(delete_cat_btn)
         
        form_layout.addRow(btn_layout)
        form_group.setLayout(form_layout)
         
        layout.addWidget(self.categories_list)
        layout.addWidget(form_group)
         
        widget.setLayout(layout)
        return widget
     
    def create_reports_tab(self):
        """Create reports tab"""
        widget = QWidget()
        layout = QVBoxLayout()
         
        # Report buttons
        report_layout = QHBoxLayout()
         
        low_stock_btn = QPushButton("Low Stock Report")
        low_stock_btn.clicked.connect(self.generate_low_stock_report)
         
        inventory_btn = QPushButton("Full Inventory Report")
        inventory_btn.clicked.connect(self.generate_inventory_report)
         
        category_btn = QPushButton("Category Report")
        category_btn.clicked.connect(self.generate_category_report)
         
        report_layout.addWidget(low_stock_btn)
        report_layout.addWidget(inventory_btn)
        report_layout.addWidget(category_btn)
         
        # Report display
        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
         
        layout.addLayout(report_layout)
        layout.addWidget(self.report_display)
         
        widget.setLayout(layout)
        return widget
     
    def refresh_all_data(self):
        """Refresh all data in the application"""
        self.load_items()
        self.load_categories()
        self.update_dashboard()
        self.statusBar().showMessage("Data refreshed", 2000)
     
    def load_items(self):
        """Load items into the table"""
        items = self.db_manager.execute_query("""
            SELECT i.id, i.name, c.name, i.quantity, i.price, i.min_stock, i.supplier, i.date_added
            FROM items i LEFT JOIN categories c ON i.category_id = c.id
        """, fetch=True)
         
        self.items_table.setRowCount(len(items) if items else 0)
         
        if items:
            for row, item in enumerate(items):
                for col, value in enumerate(item):
                    self.items_table.setItem(row, col, QTableWidgetItem(str(value or "")))
                     
                    # Highlight low stock items
                    if col == 3 and item[3] <= item[5]:  # quantity <= min_stock
                        self.items_table.item(row, col).setBackground(QColor(255, 200, 200))
     
    def load_categories(self):
        """Load categories into dropdowns and lists"""
        categories = self.db_manager.execute_query("SELECT id, name FROM categories", fetch=True)
         
        # Update category dropdown in items form
        self.item_category.clear()
        self.item_category.addItem("Select Category", 0)
         
        # Update category filter
        self.category_filter.clear()
        self.category_filter.addItem("All Categories")
         
        # Update categories list
        self.categories_list.clear()
         
        if categories:
            for cat_id, cat_name in categories:
                self.item_category.addItem(cat_name, cat_id)
                self.category_filter.addItem(cat_name)
                 
                list_item = QListWidgetItem(cat_name)
                list_item.setData(Qt.UserRole, cat_id)
                self.categories_list.addItem(list_item)
     
    def update_dashboard(self):
        """Update dashboard statistics and chart"""
        # Recreate the entire dashboard to refresh all data
        dashboard_widget = self.create_dashboard()
        central_widget = self.centralWidget()
        if central_widget and central_widget.count() > 0:
            central_widget.removeTab(0)
            central_widget.insertTab(0, dashboard_widget, "Dashboard")
            central_widget.setCurrentIndex(0)
     
    def filter_items(self):
        """Filter items based on search and category"""
        search_text = self.search_input.text().lower()
        category_text = self.category_filter.currentText()
         
        for row in range(self.items_table.rowCount()):
            show_row = True
             
            # Check search text
            if search_text:
                item_name = self.items_table.item(row, 1).text().lower()
                if search_text not in item_name:
                    show_row = False
             
            # Check category filter
            if category_text != "All Categories":
                item_category = self.items_table.item(row, 2).text()
                if category_text != item_category:
                    show_row = False
             
            self.items_table.setRowHidden(row, not show_row)
     
    def add_item(self):
        """Add new item to inventory"""
        if not self.item_name.text():
            QMessageBox.warning(self, "Error", "Item name is required!")
            return
         
        category_id = self.item_category.currentData()
        if not category_id:
            QMessageBox.warning(self, "Error", "Please select a category!")
            return
         
        success = self.db_manager.execute_query("""
            INSERT INTO items (name, category_id, quantity, price, min_stock, supplier, date_added)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            self.item_name.text(),
            category_id,
            self.item_quantity.value(),
            self.item_price.value(),
            self.item_min_stock.value(),
            self.item_supplier.text(),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
         
        self.clear_item_form()
        QMessageBox.information(self, "Success", "Item added successfully!")
        self.load_items()  # Move after dialog
     
    def update_item(self):
        """Update selected item"""
        current_row = self.items_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select an item to update!")
            return
         
        item_id = self.items_table.item(current_row, 0).text()
        category_id = self.item_category.currentData()
         
        success = self.db_manager.execute_query("""
            UPDATE items SET name=?, category_id=?, quantity=?, price=?, min_stock=?, supplier=?
            WHERE id=?
        """, (
            self.item_name.text(),
            category_id,
            self.item_quantity.value(),
            self.item_price.value(),
            self.item_min_stock.value(),
            self.item_supplier.text(),
            item_id
        ))
         
        if success is not None:
            self.clear_item_form()
            self.load_items()
            QMessageBox.information(self, "Success", "Item updated successfully!")
     
    def delete_item(self):
        """Delete selected item"""
        current_row = self.items_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select an item to delete!")
            return
         
        reply = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this item?",
                                   QMessageBox.Yes | QMessageBox.No)
         
        if reply == QMessageBox.Yes:
            item_id = self.items_table.item(current_row, 0).text()
            success = self.db_manager.execute_query("DELETE FROM items WHERE id=?", (item_id,))
             
            if success is not None:
                self.load_items()
                QMessageBox.information(self, "Success", "Item deleted successfully!")
     
    def clear_item_form(self):
        """Clear item form fields"""
        self.item_name.clear()
        self.item_category.setCurrentIndex(0)
        self.item_quantity.setValue(0)
        self.item_price.setValue(0)
        self.item_min_stock.setValue(0)
        self.item_supplier.clear()
     
    def add_category(self):
        """Add new category"""
        if not self.category_name.text():
            QMessageBox.warning(self, "Error", "Category name is required!")
            return
         
        success = self.db_manager.execute_query(
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            (self.category_name.text(), self.category_description.toPlainText())
        )
         
        if success is not None:
            self.clear_category_form()
            self.load_categories()
            QMessageBox.information(self, "Success", "Category added successfully!")
     
    def update_category(self):
        """Update selected category"""
        current_item = self.categories_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select a category to update!")
            return
         
        cat_id = current_item.data(Qt.UserRole)
        success = self.db_manager.execute_query(
            "UPDATE categories SET name=?, description=? WHERE id=?",
            (self.category_name.text(), self.category_description.toPlainText(), cat_id)
        )
         
        if success is not None:
            self.clear_category_form()
            self.load_categories()
            QMessageBox.information(self, "Success", "Category updated successfully!")
     
    def delete_category(self):
        """Delete selected category"""
        current_item = self.categories_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select a category to delete!")
            return
         
        reply = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this category?",
                                   QMessageBox.Yes | QMessageBox.No)
         
        if reply == QMessageBox.Yes:
            cat_id = current_item.data(Qt.UserRole)
            success = self.db_manager.execute_query("DELETE FROM categories WHERE id=?", (cat_id,))
             
            if success is not None:
                self.clear_category_form()
                self.load_categories()
                QMessageBox.information(self, "Success", "Category deleted successfully!")
     
    def clear_category_form(self):
        """Clear category form fields"""
        self.category_name.clear()
        self.category_description.clear()
     
    def load_category_details(self, item):
        """Load category details into form"""
        cat_id = item.data(Qt.UserRole)
        category = self.db_manager.execute_query(
            "SELECT name, description FROM categories WHERE id=?", (cat_id,), fetch=True)
         
        if category:
            self.category_name.setText(category[0][0])
            self.category_description.setPlainText(category[0][1] or "")
     
    def generate_low_stock_report(self):
        """Generate low stock report"""
        items = self.db_manager.execute_query("""
            SELECT i.name, c.name, i.quantity, i.min_stock
            FROM items i LEFT JOIN categories c ON i.category_id = c.id
            WHERE i.quantity <= i.min_stock
            ORDER BY i.quantity ASC
        """, fetch=True)
         
        report = "LOW STOCK REPORT\n" + "="*50 + "\n\n"
         
        if items:
            for name, category, quantity, min_stock in items:
                report += f"Item: {name}\n"
                report += f"Category: {category or 'N/A'}\n"
                report += f"Current Stock: {quantity}\n"
                report += f"Minimum Stock: {min_stock}\n"
                report += "-" * 30 + "\n"
        else:
            report += "No items are currently low in stock.\n"
         
        self.report_display.setText(report)
     
    def generate_inventory_report(self):
        """Generate full inventory report"""
        items = self.db_manager.execute_query("""
            SELECT i.name, c.name, i.quantity, i.price, i.supplier
            FROM items i LEFT JOIN categories c ON i.category_id = c.id
            ORDER BY i.name
        """, fetch=True)
         
        report = "FULL INVENTORY REPORT\n" + "="*50 + "\n\n"
        total_value = 0
         
        if items:
            for name, category, quantity, price, supplier in items:
                value = quantity * price
                total_value += value
                 
                report += f"Item: {name}\n"
                report += f"Category: {category or 'N/A'}\n"
                report += f"Quantity: {quantity}\n"
                report += f"Price: ${price:.2f}\n"
                report += f"Total Value: ${value:.2f}\n"
                report += f"Supplier: {supplier or 'N/A'}\n"
                report += "-" * 30 + "\n"
             
            report += f"\nTOTAL INVENTORY VALUE: ${total_value:.2f}\n"
        else:
            report += "No items in inventory.\n"
         
        self.report_display.setText(report)
     
    def generate_category_report(self):
        """Generate category-wise report"""
        categories = self.db_manager.execute_query("""
            SELECT c.name, COUNT(i.id) as item_count, SUM(i.quantity * i.price) as total_value
            FROM categories c LEFT JOIN items i ON c.id = i.category_id
            GROUP BY c.id, c.name
            ORDER BY total_value DESC
        """, fetch=True)
         
        report = "CATEGORY REPORT\n" + "="*50 + "\n\n"
         
        if categories:
            for name, item_count, total_value in categories:
                report += f"Category: {name}\n"
                report += f"Number of Items: {item_count or 0}\n"
                report += f"Total Value: ${total_value or 0:.2f}\n"
                report += "-" * 30 + "\n"
        else:
            report += "No categories found.\n"
         
        self.report_display.setText(report)
     
    def export_to_excel(self):
        """Export inventory data to Excel"""
        try:
            items = self.db_manager.execute_query("""
                SELECT i.name, c.name, i.quantity, i.price, i.min_stock, i.supplier, i.date_added
                FROM items i LEFT JOIN categories c ON i.category_id = c.id
            """, fetch=True)
             
            if not items:
                QMessageBox.warning(self, "Warning", "No data to export!")
                return
             
            df = pd.DataFrame(items, columns=[
                'Item Name', 'Category', 'Quantity', 'Price', 'Min Stock', 'Supplier', 'Date Added'
            ])
             
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Excel File", "inventory_export.xlsx", "Excel Files (*.xlsx)")
             
            if filename:
                df.to_excel(filename, index=False)
                QMessageBox.information(self, "Success", f"Data exported to {filename}")
                 
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
     
    def export_to_pdf(self):
        """Export inventory data to PDF"""
        try:
            items = self.db_manager.execute_query("""
                SELECT i.name, c.name, i.quantity, i.price, i.min_stock, i.supplier
                FROM items i LEFT JOIN categories c ON i.category_id = c.id
            """, fetch=True)
             
            if not items:
                QMessageBox.warning(self, "Warning", "No data to export!")
                return
             
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save PDF File", "inventory_export.pdf", "PDF Files (*.pdf)")
             
            if filename:
                c = canvas.Canvas(filename, pagesize=letter)
                width, height = letter
                 
                # Title
                c.setFont("Helvetica-Bold", 16)
                c.drawString(50, height - 50, "Inventory Report")
                c.drawString(50, height - 70, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                 
                # Headers
                y_position = height - 120
                c.setFont("Helvetica-Bold", 10)
                headers = ["Item", "Category", "Qty", "Price", "Min Stock", "Supplier"]
                x_positions = [50, 150, 250, 300, 350, 420]
                 
                for i, header in enumerate(headers):
                    c.drawString(x_positions[i], y_position, header)
                 
                # Data
                c.setFont("Helvetica", 9)
                y_position -= 20
                 
                for item in items:
                    if y_position < 50:  # New page if needed
                        c.showPage()
                        y_position = height - 50
                     
                    for i, value in enumerate(item):
                        text = str(value or "")[:15]  # Truncate long text
                        c.drawString(x_positions[i], y_position, text)
                     
                    y_position -= 15
                 
                c.save()
                QMessageBox.information(self, "Success", f"PDF exported to {filename}")
                 
        except Exception as e:
            QMessageBox.critical(self, "Error", f"PDF export failed: {str(e)}")
     
    def logout(self):
        """Logout and show login dialog"""
        reply = QMessageBox.question(self, "Confirm Logout", "Are you sure you want to logout?",
                                   QMessageBox.Yes | QMessageBox.No)
         
        if reply == QMessageBox.Yes:
            self.close()
            self.__init__()
            self.show()
 
# Application Entry Point
def main():
    app = QApplication(sys.argv)
     
    # Set application properties
    app.setApplicationName("Advanced Inventory Management System")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("InventoryPro")
     
    # Set application icon (if available)
    app.setWindowIcon(QIcon())
     
    # Create and show main window
    window = InventoryApp()
    window.show()
     
    # Start event loop
    sys.exit(app.exec_())
 
if __name__ == "__main__":
    main()
