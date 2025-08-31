# Advanced Inventory Management System

This is a comprehensive inventory management system built with Python and PyQt5. It provides a graphical user interface to manage inventory, track stock levels, and generate reports.

## Features

*   **User Authentication:** Secure login system with roles (admin/user).
*   **Dashboard:** An interactive dashboard with key statistics, including total items, low stock items, and total categories. It also features a bar chart for visualizing stock levels.
*   **Item Management:** Add, edit, and delete items in the inventory. Each item can have a name, category, quantity, price, minimum stock level, and supplier.
*   **Category Management:** Organize items by creating, updating, and deleting categories.
*   **Reporting:** Generate various reports, including:
    *   Low stock report
    *   Full inventory report
    *   Category-wise report
*   **Exporting:** Export inventory data to Excel (.xlsx) and PDF (.pdf) formats.
*   **Search and Filter:** Easily search for items and filter them by category.
*   **Dark/Light Theme:** Toggle between a dark and light theme for the user interface.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/inventory-management-system.git
    cd inventory-management-system
    ```

2.  **Install the dependencies:**
    This project requires the following Python libraries:
    *   PyQt5
    *   pandas
    *   matplotlib
    *   reportlab

    You can install them using pip:
    ```bash
    pip install PyQt5 pandas matplotlib reportlab
    ```

## Usage

To run the application, execute the `main.py` file:

```bash
python main.py
```

The default login credentials are:
*   **Username:** admin
*   **Password:** admin

## Dependencies

*   [PyQt5](https://pypi.org/project/PyQt5/)
*   [pandas](https://pypi.org/project/pandas/)
*   [matplotlib](https://pypi.org/project/matplotlib/)
*   [reportlab](https://pypi.org/project/reportlab/)
