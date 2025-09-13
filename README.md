# Employee Management Web Application | Flask + Oracle APEX

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.x-green.svg)
![Oracle APEX](https://img.shields.io/badge/Oracle-APEX-orange.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 📌 Project Description

The Employee Management Web Application is a hybrid solution built with **Flask (Python)** and **Oracle APEX** that demonstrates how low-code platforms and traditional web frameworks can integrate seamlessly.

The system provides two main components:

- **Flask Web App**: Enables employee login, CRUD operations, and Oracle DB connectivity using cx_Oracle
- **Oracle APEX Admin Panel**: Provides role-based access, reporting dashboards, and database management for administrators

This project showcases the ability to combine enterprise-level tooling (APEX) with open-source frameworks (Flask) for educational and enterprise use cases, developed as part of coursework at the University of the Western Cape.

---

## ✨ Features

- 🔑 **Employee Authentication**: Testable login system using selected employee IDs from database
- 🗂️ **CRUD Operations**: Add, edit, delete, and view employee details via Flask interface
- 📊 **Oracle APEX Dashboards**: Interactive forms and reports for administrative oversight
- 🔐 **Role-Based Access**: Differentiated permissions for Admin vs Employee users
- 🔄 **Database Integration**: Centralized Oracle DB backend accessible from both platforms
- 🎯 **Educational Demonstration**: Shows dual-platform development (Flask + APEX)
- ⚡ **Live Testing Environment**: Pre-configured employee records for lecturer evaluation

---

## 🛠️ Technologies Used

- **Backend**: Flask, Python 3.9+
- **Database**: Oracle SQL, Oracle APEX
- **Libraries**: cx_Oracle, SQLAlchemy (optional), REST APIs
- **Frontend**: HTML5, CSS3, Bootstrap
- **Version Control**: Git & GitHub
- **Development**: Virtual environments, pip package management

---

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Flask App     │    │   Oracle         │    │   Oracle APEX   │
│   (Python)      │◄──►│   Database       │◄──►│   (Admin Panel) │
│                 │    │                  │    │                 │
│ • Employee Login│    │ • Employee Table │    │ • Forms         │
│ • CRUD Ops      │    │ • User Auth      │    │ • Reports       │
│ • Web Interface │    │ • Data Storage   │    │ • Dashboards    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

---

## 🚀 Installation Instructions

### Prerequisites

- Python 3.9 or higher
- Oracle Database (with APEX workspace configured)
- Oracle Instant Client (for cx_Oracle connectivity)
- Virtual environment support

### Setup Environment

1. **Clone the repository**
```bash
git clone https://github.com/YOUR-USERNAME/employee-management-flask-apex.git
cd employee-management-flask-apex
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install flask cx_Oracle
# Or use: pip install -r requirements.txt
```

4. **Configure database connection**
Update your Flask app configuration with Oracle DB credentials:
```python
dsn = cx_Oracle.makedsn("host", "port", service_name="ORCL")
connection = cx_Oracle.connect(user="username", password="password", dsn=dsn)
```

5. **Initialize database schema**
```sql
CREATE TABLE employees (
    employee_id INT PRIMARY KEY,
    first_name VARCHAR2(50),
    last_name VARCHAR2(50),
    role VARCHAR2(50),
    hire_date DATE DEFAULT SYSDATE
);
```

6. **Run Flask application**
```bash
flask run
# Access at: http://127.0.0.1:5000
```

---

## 💻 Usage

### Flask Web Application
- **Employee Login**: Use pre-configured employee IDs for testing
- **View Records**: Browse employee information and details
- **CRUD Operations**: Add, edit, delete employee records (admin only)
- **Session Management**: Secure login/logout functionality

### Oracle APEX Admin Panel
- **Administrative Access**: Lecturer/admin users can manage the database
- **Interactive Forms**: Create and modify employee records
- **Reporting Dashboard**: View analytics and employee statistics
- **Role Management**: Configure user permissions and access levels

### Testing Workflow
1. Start Flask application (`flask run`)
2. Navigate to login page
3. Use provided test employee IDs to authenticate
4. Perform CRUD operations to demonstrate functionality
5. Access APEX workspace for administrative tasks

---

## 📂 Repository Structure

```
employee-management-flask-apex/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── config.py             # Database configuration
├── static/               # CSS, JavaScript files
│   ├── css/
│   └── js/
├── templates/            # HTML templates
│   ├── login.html
│   ├── dashboard.html
│   └── employee_form.html
├── sql/                  # Database scripts
│   ├── schema.sql        # Table creation
│   └── sample_data.sql   # Test employee records
├── apex-export/          # APEX application exports
│   └── apex_app.sql
├── docs/                 # Documentation and screenshots
├── .gitignore           # Git ignore rules
├── LICENSE              # MIT License
└── README.md            # This file
```

---

## 🔒 Security & Best Practices

### Data Privacy
- **No Sensitive Data**: Test environment uses dummy employee records
- **Secure Connections**: Recommended HTTPS for production deployment
- **Session Management**: Flask sessions with secure secret keys
- **Input Validation**: SQL injection protection through parameterized queries

### Development Guidelines
- **Environment Variables**: Database credentials stored separately
- **Error Handling**: Comprehensive exception management
- **Logging**: Application activity monitoring
- **Testing**: Unit tests for CRUD operations

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Create a Pull Request

### Development Setup
- Follow PEP 8 style guidelines
- Include unit tests for new functionality
- Update documentation as needed
- Test both Flask and APEX integration

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

### Academic Context
- **Institution**: University of the Western Cape
- **Course**: Database Systems & Web Development
- **Purpose**: Demonstrate integration between modern web frameworks and enterprise database platforms

### Technical Resources
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Oracle APEX Documentation](https://docs.oracle.com/en/database/oracle/application-express/)
- [cx_Oracle Library](https://cx-oracle.readthedocs.io/)

---

## 📞 Contact

**Author**: Sangesonke Njameni
**Email**: sangesonkenjameni5@gmail.com
**Institution**: University of the Western Cape

For questions, suggestions, or collaborations, please open an issue or contact through GitHub.

---

*This project demonstrates practical integration of Flask web development with Oracle's enterprise APEX platform, showcasing full-stack development skills and database connectivity in an educational context.*
