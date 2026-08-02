from flask import render_template, current_app as app

@app.route('/')
def home():
    """الصفحة الرئيسية للموقع"""
    return render_template('home.html')

@app.route('/resume')
def resume():
    """
    صفحة السيرة الذاتية:
    نقوم بطلب بيانات السيرة الذاتية من قاعدة البيانات المربوطة بالتطبيق (app.db)
    ثم نمرر هذه البيانات لملف HTML لتقوم الصفحة بعرض الخبرات والمهارات
    """
    resume_data = app.db.getResumeData()
    return render_template('resume.html', resume=resume_data)