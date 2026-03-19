from email.mime.application import MIMEApplication
from flask import Flask, request, jsonify, send_file, send_from_directory, render_template, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime
from email.utils import formataddr
import threading
import razorpay
import random
from dotenv import load_dotenv
from basic_paper_evaluator import paper_evaluation_process
from firebase_store import (
    create_paper,
    get_paper_by_credentials,
    get_paper_by_id,
    initialize_firebase,
    update_paper,
)

app = Flask(__name__, template_folder='templates', static_folder='static')
load_dotenv()

def generate_unique_paper_id(max_attempts=20):
    """Generate a unique paper ID by checking existing Firestore documents."""
    current_year = datetime.now().year

    for _ in range(max_attempts):
        random_num = random.randint(1000, 9999)
        paper_id = f"ISIRP-{current_year}-{random_num}"
        if not get_paper_by_id(paper_id):
            return paper_id

    raise RuntimeError("Could not generate a unique paper ID. Please retry.")

# Razorpay configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

@app.route('/files/<filename>')
def download_file(filename):
    """Serve static files from the files directory"""
    return send_from_directory('static/files', filename)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    
# Email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')

def send_confirmation_email(to_email, paper_id, submission_date):
    subject = 'Your Research Paper Submission Confirmation'
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
        
        <div style="text-align: center; margin-bottom: 30px;">
            
            <h2 style="color: #2c3e50;">ISIRP - Research Submission Confirmation</h2>
        </div>

        <p style="font-size: 16px; color: #333333;">Dear Researcher,</p>

        <p style="font-size: 16px; color: #333333;">
            We are pleased to inform you that your research paper has been successfully submitted on <strong>{submission_date}</strong> to the <strong>International Scientific and Innovative Research Publications (ISIRP)</strong>.
        </p>

        <p style="font-size: 16px; color: #333333;">
            <strong>Submission Details:</strong><br>
            <b>Paper ID:</b> {paper_id}<br>
            <b>Submission Date:</b> {submission_date}
        </p>

        <p style="font-size: 16px; color: #333333;">
            Kindly retain this Paper ID for future correspondence. Our editorial board will now begin the review process. You can expect a response within the next <strong>1-2 Hours.</strong>.
        </p>

        <p style="font-size: 16px; color: #333333;">
            If you have any questions or need further assistance, please do not hesitate to contact us at <a href="mailto:teamisirp@gmail.com">teamisirp@gmail.com</a>.
        </p>

        <p style="font-size: 16px; color: #333333;">
            Thank you for choosing ISIRP to publish your work. We look forward to reviewing your submission.
        </p>

        <p style="font-size: 16px; color: #333333;">
            Best regards,<br>
            <strong>Editorial Team</strong><br>
            ISIRP
        </p>

        <hr style="margin-top: 30px; border: none; border-top: 1px solid #dddddd;">

        <p style="font-size: 12px; color: #888888; text-align: center;">
            © 2025 ISIRP. All rights reserved.<br>
            Visit us at <a href="https://isirp.tech" style="color: #888888;">www.isirp.tech</a>
        </p>

        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["From"] = formataddr(("ISIRP", EMAIL_ADDRESS))
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
    
def send_certificates_email(to_email, paper_id, certificate_paths):
    subject = 'Your Research Paper Certificates'
    body = f"""
    <html>
    <body>
        <h2>Thank You for Your Submission!</h2>
        <p>Your research paper (ID: {paper_id}) has been processed successfully.</p>
        <p>Attached are the certificates for all authors. Please download and distribute them to your co-authors.</p>
        <p>Best regards,<br>ISIRP Team</p>
    </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg["From"] = formataddr(("ISIRP", EMAIL_ADDRESS))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    
    # Attach certificates
    for path in certificate_paths:
        with open(path, 'rb') as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(path))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
        msg.attach(part)
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Certificate email failed: {e}")
        return False

# Serve index.html as the main page
@app.route('/')
def home():
    return render_template('index.html')

# Serve submit.html
@app.route('/submit')
def submit_form():
    return render_template('submit.html')

# Existing routes for terms, privacy, etc.
@app.route('/termsandconditions')
def terms():
    return render_template('termsandconditions.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')

@app.route('/return')
def return_policy():
    return render_template('return.html')

@app.route('/refund')
def refund():
    return render_template('refund.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/dashboard')
def dashboard():
    """Serve the dashboard template"""
    return render_template('dashboard.html')

@app.route('/submissionagreement')
def submissionagreement():
    """Serve the dashboard template"""
    return render_template('submissionagreement.html')

@app.route('/AIReviewprocess')
def AIReviewprocess():
    """Serve the dashboard template"""
    return render_template('AIReviewprocess.html')

# Payment-related routes
@app.route('/create-order', methods=['POST'])
def create_order():
    """Create Razorpay order for payment"""
    data = request.json
    
    try:
        # Create Razorpay order (amount is in paise: 20000 paise = ₹200)
        order_data = {
            'amount': 20000,  # ₹200 in paise
            'currency': 'INR',
            'payment_capture': '1'  # Auto-capture payment
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        return jsonify({
            'success': True,
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency'],
            'key_id': RAZORPAY_KEY_ID
        })
    except Exception as e:
        print(f"Error creating order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    """Verify Razorpay payment signature and update paper status"""
    data = request.json
    
    params_dict = {
        'razorpay_payment_id': data['razorpay_payment_id'],
        'razorpay_order_id': data['razorpay_order_id'],
        'razorpay_signature': data['razorpay_signature']
    }
    
    try:
        # Verify payment signature
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        paper_id = data.get('paper_id')
        if not paper_id:
            return jsonify({'success': False, 'error': 'Paper ID missing'}), 400

        # Find the paper in Firestore
        paper = get_paper_by_id(paper_id)
        if not paper:
             return jsonify({'success': False, 'error': 'Paper not found'}), 404
        
        # Update payment status
        update_paper(paper_id, {
            'payment_status': 'completed',
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature'],
        })

        # Re-fetch updated payload for downstream usage
        paper = get_paper_by_id(paper_id)
        
        # Send confirmation email
        send_confirmation_email(
            paper.get('corresponding_author_email'),
            paper.get('paper_id'),
            paper.get('submission_date')
        )
        
        # Start background processes with delays
        # Delay for Paper Evaluation Email: 1 hour (3600 seconds)
        if paper.get('manuscript_filename'):
            file_path = os.path.join(UPLOAD_FOLDER, paper.get('manuscript_filename'))
            eval_timer = threading.Timer(
                3600,  # 1 hour delay
                paper_evaluation_process,
                args=(paper.get('paper_id'), file_path, paper.get('corresponding_author_email'))
            )
            eval_timer.start()

        # Delay for Certificate Generation: 1.5 hours (5400 seconds)
        cert_timer = threading.Timer(
            1800,  # 1.5 hours delay
            generate_certificates_background,
            args=(paper.get('paper_id'),)
        )
        cert_timer.start()
        
        return jsonify({'success': True, 'paper_id': paper.get('paper_id')})
        
    except razorpay.errors.SignatureVerificationError as e:
        print(f"Payment verification failed: {e}")
        return jsonify({'success': False, 'error': 'Payment verification failed'}), 400
    except Exception as e:
        print(f"Error verifying payment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/payment-success')
def payment_success():
    """Display payment success page"""
    paper_id = request.args.get('paper_id')
    return render_template('payment_success.html', paper_id=paper_id)

@app.route('/payment-failed')
def payment_failed():
    """Display payment failed page"""
    return render_template('payment_failed.html')

# Updated submission endpoint that saves data temporarily without payment
@app.route('/prepare-submission', methods=['POST'])
def prepare_submission():
    """Save submission data and file before payment"""
    try:
        # Check if file part is present
        if 'manuscript' not in request.files:
             return jsonify({'success': False, 'error': 'No file part'}), 400
        
        file = request.files['manuscript']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'}), 400
            
        # Get other form data
        # Note: In multipart/form-data, numbers are strings like '1', '2'
        paper_title = request.form.get('paper_title')
        corresponding_author_name = request.form.get('corresponding_author_name')
        corresponding_author_email = request.form.get('corresponding_author_email')
        
        # Validate required fields
        if not paper_title or not corresponding_author_name or not corresponding_author_email:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Save file
        import werkzeug
        filename = werkzeug.utils.secure_filename(file.filename)
        # Ensure unique filename to prevent overwrite
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        # Generate unique paper ID
        paper_id = generate_unique_paper_id()
        submission_date = datetime.now().strftime('%Y-%m-%d')

        create_paper(paper_id, {
            'paper_title': paper_title,
            'corresponding_author_name': corresponding_author_name,
            'corresponding_author_email': corresponding_author_email,
            'additional_author_name_1': request.form.get('additional_author_name_1'),
            'additional_author_name_2': request.form.get('additional_author_name_2'),
            'additional_author_name_3': request.form.get('additional_author_name_3'),
            'additional_author_name_4': request.form.get('additional_author_name_4'),
            'additional_author_name_5': request.form.get('additional_author_name_5'),
            'corresponding_author_certificate': None,
            'additional_author_cert_1': None,
            'additional_author_cert_2': None,
            'additional_author_cert_3': None,
            'additional_author_cert_4': None,
            'additional_author_cert_5': None,
            'submission_date': submission_date,
            'manuscript_filename': filename,
            'payment_status': 'pending',
            'razorpay_order_id': None,
            'razorpay_payment_id': None,
            'razorpay_signature': None,
        })
        
        return jsonify({'success': True, 'paper_id': paper_id})
        
    except Exception as e:
        print(f"Error in prepare_submission: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Serve static files (CSS, JS, images)
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Login API
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    paper_id = data.get('paper_id')
    email = data.get('email')
    
    # Validate input
    if not paper_id or not email:
        return jsonify({'success': False, 'error': 'Missing paper ID or email'}), 400
    
    # Query Firestore
    paper = get_paper_by_credentials(paper_id, email)
    
    if paper:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

# Dashboard data API
@app.route('/api/dashboard-data', methods=['POST'])
def api_dashboard_data():
    data = request.json
    paper_id = data.get('paper_id')
    email = data.get('email')
    
    paper = get_paper_by_credentials(paper_id, email)
    
    if not paper:
        return jsonify({'success': False, 'error': 'Paper not found'}), 404
    
    # Convert paper data to dictionary
    paper_data = {
        'paper_title': paper.get('paper_title'),
        'corresponding_author_name': paper.get('corresponding_author_name'),
        'corresponding_author_email': paper.get('corresponding_author_email'),
        'paper_id': paper.get('paper_id'),
        'submission_date': paper.get('submission_date'),
        'corresponding_author_certificate': paper.get('corresponding_author_certificate'),
        'additional_author_name_1': paper.get('additional_author_name_1'),
        'additional_author_name_2': paper.get('additional_author_name_2'),
        'additional_author_name_3': paper.get('additional_author_name_3'),
        'additional_author_name_4': paper.get('additional_author_name_4'),
        'additional_author_name_5': paper.get('additional_author_name_5'),
        'additional_author_cert_1': paper.get('additional_author_cert_1'),
        'additional_author_cert_2': paper.get('additional_author_cert_2'),
        'additional_author_cert_3': paper.get('additional_author_cert_3'),
        'additional_author_cert_4': paper.get('additional_author_cert_4'),
        'additional_author_cert_5': paper.get('additional_author_cert_5'),
        'payment_status': paper.get('payment_status')
    }
    
    return jsonify({'success': True, 'paper': paper_data})

# Certificate download endpoint
@app.route('/download-certificate')
def download_certificate():
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'Missing path parameter'}), 400
    
    try:
        return send_file(path, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

# @app.route('/papers')
# def show_papers():
#     search_query = request.args.get('q', '')
#     
#     if search_query:
#         papers = ResearchPaper.query.filter(
#             (ResearchPaper.paper_title.ilike(f'%{search_query}%')) |
#             (ResearchPaper.corresponding_author_name.ilike(f'%{search_query}%')) |
#             (ResearchPaper.additional_author_name_1.ilike(f'%{search_query}%')) |
#             (ResearchPaper.additional_author_name_2.ilike(f'%{search_query}%')) |
#             (ResearchPaper.additional_author_name_3.ilike(f'%{search_query}%')) |
#             (ResearchPaper.additional_author_name_4.ilike(f'%{search_query}%')) |
#             (ResearchPaper.additional_author_name_5.ilike(f'%{search_query}%'))
#         ).all()
#     else:
#         papers = ResearchPaper.query.all()
#     
#     paper_list = []
#     for paper in papers:
#         description = f"Research paper titled '{paper.paper_title[:70]}{'...' if len(paper.paper_title) > 70 else ''}'"
#         
#         paper_list.append({
#             'title': paper.paper_title,
#             'corresponding_author': paper.corresponding_author_name,
#             'paper_id': paper.paper_id,
#             'submission_date': paper.submission_date,
#             'description': description
#         })
#     
#     return render_template('papers.html', papers=paper_list, search_query=search_query)

@app.route('/view-paper/<paper_id>')
def view_paper(paper_id):
    paper = get_paper_by_id(paper_id)
    
    if not paper:
        return "Paper not found", 404

@app.route('/AboutThisProject')
def about_project():
    return render_template('AboutThisProject.html')
    
    file_path = os.path.join(UPLOAD_FOLDER, paper.manuscript_filename)
    
    if not os.path.exists(file_path):
        return "File not found", 404
    
    return send_file(file_path, as_attachment=False)

def generate_certificates_background(paper_id):
    # This will run in a separate thread
    from certificate_generator import generate_certificates
    generate_certificates(paper_id)

if __name__ == '__main__':
    initialize_firebase()
    print("Firebase initialized successfully")
    print("Server starting on http://127.0.0.1:5000")
    
    app.run(debug=True, port=5000)