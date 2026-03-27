# 🚀 Koby's AI Assistant - Advanced PDF Q&A System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Django](https://img.shields.io/badge/Django-4.0+-green.svg)
![AI](https://img.shields.io/badge/AI-Powered-orange.svg)
![PDF](https://img.shields.io/badge/PDF-Processing-red.svg)
![Supabase](https://img.shields.io/badge/Supabase-Database%2BStorage-green.svg)
![FAISS](https://img.shields.io/badge/FAISS-Vector%20Search-purple.svg)

**A comprehensive Django-based PDF Question-Answering system with AI-powered search, user authentication, admin dashboard, and collaborative knowledge enhancement.**

[![GitHub stars](https://img.shields.io/github/stars/itsSparsh10/Koby-s-Ai-Assistant)](https://github.com/itsSparsh10/Koby-s-Ai-Assistant/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/itsSparsh10/Koby-s-Ai-Assistant)](https://github.com/itsSparsh10/Koby-s-Ai-Assistant/network)
[![GitHub issues](https://img.shields.io/github/issues/itsSparsh10/Koby-s-Ai-Assistant)](https://github.com/itsSparsh10/Koby-s-Ai-Assistant/issues)

</div>

---

## ✨ Features

### 🎯 **Core AI Features**
- **📄 PDF Processing**: Intelligent text extraction and chunking from PDF documents
- **🤖 AI-Powered Q&A**: Google Gemini 2.0 Flash integration for intelligent responses
- **🔍 Semantic Search**: FAISS vector search with similarity matching
- **🎤 Voice Input**: Speech-to-text functionality for hands-free interaction
- **📷 Image Search**: Visual content analysis and search capabilities
- **🧠 Smart Chunking**: Advanced text segmentation with overlap optimization

### 👥 **User Management**
- **🔐 Authentication System**: Secure user registration and login
- **👤 Role-Based Access**: Admin, Manager, and User roles with different permissions
- **📊 Session Tracking**: Real-time user activity monitoring
- **🔒 Security**: Password hashing, CSRF protection, and secure sessions

### 🏢 **Admin Dashboard**
- **📈 Analytics**: Comprehensive system statistics and user metrics
- **👥 User Management**: Create, manage, and monitor user accounts
- **📄 Document Management**: Upload, process, and manage PDF documents
- **💬 Contribution Moderation**: Review and approve user contributions
- **📊 Live Monitoring**: Real-time user sessions and activity tracking

### 🤝 **Collaborative Features**
- **💡 User Contributions**: Community-driven knowledge enhancement
- **⭐ Rating System**: Quality assessment for user contributions
- **🔍 Enhanced Search**: Combines original documents with user contributions
- **📝 Feedback System**: User feedback collection and analysis
- **🎯 Smart Prioritization**: AI-powered result ranking and prioritization

### 🎨 **User Experience**
- **📱 Responsive Design**: Modern, mobile-friendly interface
- **⚡ Real-time Results**: Fast search and response times
- **🎭 Modern UI**: Clean, intuitive design with smooth animations
- **🌙 Dark Mode Ready**: Theme support for different preferences

---

## 🏗️ Architecture

### **Backend Stack**
- **Django 4.2+**: Web framework with REST API
- **Django REST Framework**: API development
- **SQLite + Supabase**: Application DB with Supabase vector/search storage
- **FAISS**: Vector similarity search
- **Sentence Transformers**: Text embeddings
- **Google Gemini AI**: Language model integration

### **Frontend Stack**
- **Vanilla JavaScript**: Modern ES6+ features
- **CSS3**: Responsive design with animations
- **HTML5**: Semantic markup and accessibility

### **AI & ML Stack**
- **Google Gemini 2.0 Flash**: Primary AI language model
- **Sentence Transformers**: Text embedding generation
- **FAISS**: Vector database for similarity search
- **PyPDF2**: PDF text extraction

---

## 🚀 Quick Start

### **Prerequisites**
- Python 3.8+
- Git
- Google Gemini API Key (optional but recommended)

### **Installation**

1. **Clone the repository**
```bash
git clone https://github.com/itsSparsh10/Koby-s-Ai-Assistant.git
cd Koby-s-Ai-Assistant
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment setup**
```bash
# Create .env file
cp env_template.txt .env
# Edit .env with your configuration
```

5. **Database setup**
```bash
python manage.py makemigrations
python manage.py migrate
python setup_database.py  # Create initial admin user
```

6. **Process PDFs**
```bash
python manage.py embed_pdfs
```

7. **Start server**
```bash
python manage.py runserver
# Or use the startup script
python start_server.py
```

8. **Access the application**
- Main Interface: http://localhost:8000/
- Admin Dashboard: http://localhost:8000/admin/
- API Documentation: http://localhost:8000/api/

---

## Supabase Setup

1. Create a Supabase project and run `supabase_schema.sql` in SQL Editor.
2. Enable extensions: `vector`, `pgcrypto`.
3. Create Storage bucket `pdfs` (private).
4. Set env vars:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_PDF_BUCKET=pdfs`
5. Use endpoints:
   - `POST /api/admin/upload-signing/` (create signed upload URL)
   - `POST /api/admin/upload-pdf/` (direct upload + documents row)
   - `POST /api/admin/start-ingestion/` (chunk + embed + insert `document_chunks`)
   - `POST /api/ask-supabase/` (RPC search via `match_document_chunks`)

### Vercel Env Vars

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (server only)
- `GEMINI_API_KEY` (server only)

---

## ⚙️ Configuration

### **Environment Variables (.env)**
   ```env
# Django Configuration
DJANGO_SECRET_KEY=your-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1,*
   
# AI Configuration
GEMINI_API_KEY=your-gemini-api-key-here

# PDF Processing
   PDF_DIRECTORY=pdfs
   INDEX_PATH=indexes/faiss_index.bin
   METADATA_PATH=indexes/metadata.json
   CHUNK_SIZE=1000
   CHUNK_OVERLAP=200
   EMBED_MODEL_NAME=all-MiniLM-L6-v2
   
# Search Configuration
   MAX_SEARCH_RESULTS=5
   SIMILARITY_THRESHOLD=0.3

# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-or-publishable-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_PDF_BUCKET=pdfs
```

---

## 📚 API Documentation

### **Authentication Endpoints**
```http
POST /api/auth/login/          # User login
POST /api/auth/register/       # User registration
GET  /api/auth/check/          # Check authentication status
POST /api/auth/logout/         # User logout
POST /api/auth/create-user/    # Create user with role
```

### **Search Endpoints**
```http
POST /api/ask/                 # Text-based Q&A
POST /api/image-search/        # Image-based search
GET  /api/health/              # System health check
GET  /api/documents/           # List indexed documents
```

### **Admin Endpoints**
```http
GET  /api/admin/dashboard-stats/           # Dashboard statistics
POST /api/admin/upload-pdf/                # Upload PDF documents
GET  /api/admin/list-users/                # List all users
POST /api/admin/create-user/               # Create new user
GET  /api/admin/contributions/             # List user contributions
POST /api/admin/contributions/approve/     # Approve contribution
```

### **Analytics Endpoints**
```http
GET  /api/auth/stats/                      # User statistics
GET  /api/auth/live-users/                 # Live user count
GET  /api/feedback/analytics/              # Feedback analytics
GET  /api/feedback/top-contributions/      # Top contributions
```

---

## 🎯 Usage Guide

### **For End Users**

1. **Create Account**: Register with name, email, and password
2. **Login**: Access your personalized dashboard
3. **Search**: Ask questions about your PDF documents
4. **Voice Search**: Use microphone for hands-free interaction
5. **Image Search**: Upload images for visual content analysis
6. **Contribute**: Add your knowledge to help others

### **For Administrators**

1. **Dashboard**: Monitor system health and user activity
2. **User Management**: Create and manage user accounts
3. **Document Management**: Upload and process PDF documents
4. **Content Moderation**: Review and approve user contributions
5. **Analytics**: Track usage patterns and system performance

---

## 🏗️ Project Structure

```
📁 Koby-s-Ai-Assistant/
├── 📄 core/                    # Main Django app
│   ├── 📁 authentication/      # Auth utilities
│   ├── 📁 management/          # Django commands
│   ├── 📁 models/              # Data models
│   ├── 📁 serializers/         # API serializers
│   ├── 📄 models.py            # User and data models
│   ├── 📄 views.py             # API views and endpoints
│   ├── 📄 urls.py              # URL routing
│   ├── 📄 utils.py             # Core utilities
│   ├── 📄 enhanced_search.py   # Advanced search logic
│   ├── 📄 supabase_utils.py    # Supabase integration
│   └── 📄 session_utils.py     # Session management
├── 📄 pdf_qa/                  # Django project settings
│   ├── 📄 settings.py          # Configuration
│   ├── 📄 urls.py              # Main URL routing
│   └── 📄 wsgi.py              # WSGI configuration
├── 📁 templates/               # HTML templates
├── 📁 static/                  # CSS, JS, images
├── 📁 pdfs/                    # PDF documents storage
├── 📁 indexes/                 # FAISS index and metadata
├── 📄 manage.py                # Django management
├── 📄 requirements.txt         # Python dependencies
├── 📄 start_server.py          # Startup script
└── 📄 setup_database.py        # Database initialization
```

---

## 🔧 Advanced Features

### **Enhanced Search System**
- **Dual Search**: Combines FAISS vector search with Supabase contributions
- **Smart Prioritization**: AI-powered result ranking
- **Fallback Mechanisms**: Graceful degradation when services are unavailable
- **Quality Assessment**: Automatic evaluation of search result quality

### **User Contribution System**
- **Knowledge Enhancement**: Users can add their expertise
- **Rating System**: Community-driven quality control
- **Moderation Tools**: Admin approval workflow
- **Analytics**: Track contribution effectiveness

### **Session Management**
- **Real-time Tracking**: Monitor active user sessions
- **Activity Logging**: Track user interactions
- **Session Analytics**: Usage pattern analysis
- **Security Monitoring**: Detect suspicious activity

---

## 🚨 Troubleshooting

### **Common Issues**

**Database Connection Error**
```bash
python manage.py migrate
python setup_database.py
```

**PDF Processing Issues**
```bash
python manage.py embed_pdfs --force
```

**AI Service Not Working**
- Check GEMINI_API_KEY in .env file
- Verify API key is valid and has sufficient quota

**Search Not Working**
- Ensure PDFs are processed: `python manage.py embed_pdfs`
- Check if indexes exist in `indexes/` directory

### **Performance Optimization**

1. **Memory Usage**: Adjust batch size in PDF processing
2. **Search Speed**: Tune similarity threshold
3. **Database**: Use Supabase Postgres + vector for large datasets
4. **Caching**: Implement Redis for frequently accessed data

---

## 🔒 Security Features

- **Password Hashing**: Secure password storage using Django's built-in hashing
- **CSRF Protection**: Cross-site request forgery protection
- **Session Security**: Secure session management with configurable timeouts
- **Input Validation**: Comprehensive input sanitization and validation
- **Role-Based Access**: Granular permission system
- **API Security**: Rate limiting and request validation

---

## 📊 Monitoring & Analytics

### **System Metrics**
- User registration and activity rates
- Search query patterns and success rates
- Document processing statistics
- System performance metrics

### **User Analytics**
- Individual user activity tracking
- Contribution quality assessment
- Session duration and frequency
- Feature usage patterns

---

## 🚀 Deployment

### **Production Considerations**

1. **Environment Variables**: Use secure, unique keys
2. **Database**: Switch to PostgreSQL or MySQL
3. **Static Files**: Configure proper static file serving
4. **HTTPS**: Enable SSL/TLS encryption
5. **Monitoring**: Set up logging and error tracking
6. **Backup**: Implement regular database backups

### **Docker Deployment**
```dockerfile
# Example Dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

---

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Gemini AI** for powerful language model capabilities
- **Django Community** for the excellent web framework
- **FAISS Team** for efficient vector search
- **Sentence Transformers** for text embedding models

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/itsSparsh10/Koby-s-Ai-Assistant/issues)
- **Discussions**: [GitHub Discussions](https://github.com/itsSparsh10/Koby-s-Ai-Assistant/discussions)
- **Email**: [Contact Developer](mailto:your-email@example.com)

---

<div align="center">

**⭐ Star this repository if you found it helpful!**

[![GitHub](https://img.shields.io/badge/GitHub-Profile-black?style=for-the-badge&logo=github)](https://github.com/itsSparsh10)
[![Star](https://img.shields.io/badge/⭐-Star%20this%20repo-yellow?style=for-the-badge)](https://github.com/itsSparsh10/Koby-s-Ai-Assistant)
[![Fork](https://img.shields.io/badge/🍴-Fork%20this%20repo-blue?style=for-the-badge)](https://github.com/itsSparsh10/Koby-s-Ai-Assistant/fork)

</div>