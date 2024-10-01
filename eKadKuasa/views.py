import io
import fitz
import qrcode
import base64
import logging

#officers

from io import BytesIO
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.timezone import now
from datetime import date
from django.db import connection
from django.http import HttpResponse
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse


from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

import qrcode
from io import BytesIO
from django.http import HttpResponse

import qrcode
import base64
from io import BytesIO
from django.db import connections
from django.core.mail import send_mail
from django.shortcuts import render
from django.conf import settings
from django.db import connection
from django.conf import settings
from django.db import connection, IntegrityError
from django.db import connection, IntegrityError
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.core.files.base import ContentFile
import base64
import imghdr
import base64
import fitz  # PyMuPDF
import qrcode
from io import BytesIO

from django.http import HttpResponse

def h(request):
    # Generate QR code for the link
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data('http://10.2.12.226:8000/officer_login/')
    qr.make(fit=True)

    # Create an image from the QR code
    img = qr.make_image(fill='black', back_color='white')

    # Save the image in a BytesIO buffer
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')  # Encode to base64

    context = {'qr_image': img_str}
    return render(request, "h.html", context)



def login(request):
    message = ''
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        with connections['default'].cursor() as cursor:
            cursor.execute("SELECT * FROM admin WHERE user = %s AND pasword = %s", [username, password])
            user = cursor.fetchone()

            if user:
                request.session['username'] = username
                return redirect('data')
            else:
                message = 'Invalid username or password.'
    return render(request, "1loginPage.html", {'message' : message})



def forgot(request):
    message = ''  # Initialize message variable
    if request.method == 'POST':
        no_siri = request.POST.get('NoSiri')
        email = request.POST.get('Email')

        # Fetch the officer's email based on NoSiri
        with connections['default'].cursor() as cursor:
            cursor.execute("""
                SELECT Email FROM officer WHERE NoSiri = %s
            """, [no_siri])
            result = cursor.fetchone()

        if result:
            existing_email = result[0]
            
            if existing_email == email:
                # Generate the reset token
                token = generate_token(no_siri)
                
                # Generate reset link
                reset_link = request.build_absolute_uri(reverse('reset_password', args=[token]))
                
                # Send the email with the reset link
                send_mail(
                    'Reset Kata Laluan - EKad Kuasa',
                    f'Sila klik pautan ini untuk menetapkan kata laluan baru anda: {reset_link}',
                    'noreply@yourdomain.com',  # Replace with your email
                    [email],
                    fail_silently=False,
                )
                message = "We've send you an email"
            else:
                message = "Invalid Email"
        else:
            message = "No. Siri not found"

    return render(request, "10UserForgot.html", {'message': message})


from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode

def reset_password(request, token):
    message = ''
    no_siri = check_token(token)  # Validate the token and get NoSiri

    if no_siri is None:
        message = "Pautan reset tidak sah atau telah tamat tempoh."
        return redirect('forgot')

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password == confirm_password:
            # Update the password in the database
            with connections['default'].cursor() as cursor:
                cursor.execute("""
                    UPDATE officer SET Password = %s WHERE NoSiri = %s
                """, [new_password, no_siri])
            
            message = "Kata laluan anda telah berjaya dikemaskini."
            return redirect('officer_login')
        else:
            message = "Kata laluan tidak sepadan."

    return render(request, "11ResetPass.html", {'message' : message})


from django.core import signing
from datetime import timedelta
from django.utils import timezone

def generate_token(no_siri):
    """Generate a token for resetting password."""
    expiration = timezone.now() + timedelta(hours=1)  # Set token validity to 1 hour
    token = signing.dumps({'NoSiri': no_siri, 'exp': expiration.isoformat()})
    return token

def check_token(token):
    """Validate the token."""
    try:
        data = signing.loads(token)
        if timezone.now().isoformat() > data['exp']:
            return None  # Token has expired
        return data['NoSiri']
    except signing.BadSignature:
        return None  # Invalid token


def data(request, filter_by='Nama', query=''):
    with connection.cursor() as cursor:
        # SQL query with filtering (adjusted for your `filter_by` field)
        query_sql = f"""
            SELECT NoSiri, Nama, Bahagian, Jawatan, Status, Profile
            FROM officer
            WHERE {filter_by} LIKE %s
        """
        # Execute the query with parameterized input to avoid SQL injection
        cursor.execute(query_sql, [f'%{query}%'])
        officers_raw = cursor.fetchall()  # Fetch all officers' data

    # Process the raw data into dictionaries for template use
    officers = []
    for row in officers_raw:
        officer = {
            'NoSiri': row[0],
            'Nama': row[1],
            'Bahagian': row[2],
            'Jawatan': row[3],
            'Status': row[4],
            'Profile': None  # Initialize Profile with None
        }
        
        # Convert base64 string to data URL for image display
        if row[5]:  # Check if Profile is not None
            # Assuming the Profile field is base64 encoded string
            officer['Profile'] = f"data:image/jpeg;base64,{row[5].decode('utf-8')}"
        
        officers.append(officer)

    # Pass the processed data to the template
    context = {
        'officers': officers
    }
    return render(request, '2dataPage.html', context)

def report(request):
    today = datetime.today()
    start_date = today.replace(day=1)
    end_date = today.replace(day=1, month=today.month % 12 + 1)  # First day of next month
    month_name = today.strftime('%B')  # Get the full month name (e.g., 'September')

    # Create a list of all days in the current month
    all_days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days)]

    with connection.cursor() as cursor:
        # Fetch the count of records for each day of the current month
        cursor.execute("""
            SELECT DAY(date) as day, COUNT(*) as count
            FROM record
            WHERE date BETWEEN %s AND %s
            GROUP BY DAY(date)
            ORDER BY DAY(date)
        """, [start_date, end_date])
        daily_counts = cursor.fetchall()

        # Fetch unique NoSiri, their corresponding names, and statuses, ensuring each officer is only listed once
        cursor.execute("""
            SELECT DISTINCT o.NoSiri, o.Nama, o.Status
            FROM officer o
            JOIN record r ON o.NoSiri = r.NoSiri
        """)
        unique_officers = cursor.fetchall()

    # Prepare data for the bar graph
    dates = list(range(1, len(all_days) + 1))
    counts = [0] * len(all_days)

    # Map the counts from the query to the corresponding day
    for day, count in daily_counts:
        counts[day - 1] = count

    context = {
        'dates': dates,
        'counts': counts,
        'unique_officers': unique_officers,  # Pass unique officers to the template
        'month_name': month_name  # Pass the month name to the template
    }

    return render(request, "3reportPage.html", context)

from django.db import connection
from datetime import datetime

from datetime import datetime, timedelta

def personal(request, no_siri):
    # Fetch the officer's data
    with connection.cursor() as cursor:
        # Fetch the officer with the given NoSiri
        cursor.execute("""
            SELECT NoSiri, Nama, NoKP, Jawatan, Bahagian, Email, Status, Profile
            FROM officer
            WHERE NoSiri = %s
        """, [no_siri])
        officer_data = cursor.fetchone()

        if officer_data is None:
            return render(request, "404.html", status=404)

        today = datetime.today()
        start_date = today.replace(day=1)
        end_date = today.replace(day=1, month=today.month % 12 + 1)  # First day of next month

        # Create a list of all days in the current month
        all_days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days)]

        # Fetch the record data for the specific officer for the current month
        cursor.execute("""
            SELECT DAY(date) as day, COUNT(*) as count
            FROM record
            WHERE NoSiri = %s AND date BETWEEN %s AND %s
            GROUP BY DAY(date)
            ORDER BY DAY(date)
        """, [no_siri, start_date, end_date])
        daily_counts = cursor.fetchall()

    # Prepare data for the bar graph (set all counts to 0 initially for all days of the month)
    dates = list(range(1, len(all_days) + 1))  # All days of the current month
    counts = [0] * len(all_days)

    # Map the counts from the query to the corresponding day
    for day, count in daily_counts:
        counts[day - 1] = count

    context = {
        'dates': dates,  # Static list of all days in the month
        'counts': counts,  # The counts mapped to the days
        'NoSiri': officer_data[0],
        'Nama': officer_data[1],
        'NoKP': officer_data[2],
        'Jawatan': officer_data[3],
        'Bahagian': officer_data[4],
        'Email': officer_data[5],
        'Status': officer_data[6],
        'Profile': f"data:image/jpeg;base64,{officer_data[7].decode('utf-8')}",
        'month_name': today.strftime('%B')  # Current month
    }

    return render(request, "4reportPersonalPage.html", context)


#download_images_zip

from django.db import connection

import base64

def approve(request):
    pending_officers = []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT NoSiri, Nama, Profile
            FROM temp_officer
            WHERE Stat = 'Pending'
        """)
        officers = cursor.fetchall()

        # Loop through officers and convert their profile image to base64
        for officer in officers:
            if officer[2]:  # Check if profile image exists
                profile_base64 = f"data:image/jpeg;base64,{officer[2].decode('utf-8')}"
            else:
                profile_base64 = None
            
            pending_officers.append({
                'NoSiri': officer[0],
                'Nama': officer[1],
                'Profile': profile_base64,
            })

    return render(request, "5approveData.html", {'pending_officers': pending_officers})


from django.db import connection
from django.core.mail import send_mail
from django.utils import timezone
from django.http import HttpResponse

from django.db import connection

from django.core.mail import send_mail
from django.utils import timezone
from django.db import connection

def extend_approve(request, no_siri):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT NoSiri, Password, Nama, NoKP, Jawatan, Bahagian, Email, Profile, Sign, Stat
            FROM temp_officer
            WHERE NoSiri = %s
        """, [no_siri])
        officer_data = cursor.fetchone()

    if officer_data:
        context = {
            'NoSiri': officer_data[0],
            'Password': officer_data[1],
            'Nama': officer_data[2],
            'NoKP': officer_data[3],
            'Jawatan': officer_data[4],
            'Bahagian': officer_data[5],
            'Email': officer_data[6],
            'Profile': f"data:image/jpeg;base64,{officer_data[7].decode('utf-8')}",
            'Sign': f"data:image/jpeg;base64,{officer_data[8].decode('utf-8')}",
            'Stat': officer_data[9]
        }
        return render(request, '5extend_approve.html', context)
    else:
        return render(request, '5extend_approve.html', {'error': 'Officer not found'})
    
from django.core.mail import send_mail

from django.core.mail import send_mail
from django.db import connection
import time

def approve_action(request, no_siri):
    if request.method == "POST":
        # Get the PDF file (Kad Kuasa)
        kadkuasa_file = request.FILES.get('kadkuasa')

        if kadkuasa_file:
            with connection.cursor() as cursor:
                # Fetch officer data from temp_officer
                cursor.execute("""
                    SELECT NoSiri, Password, Nama, NoKP, Jawatan, Bahagian, Email, Profile, Sign
                    FROM temp_officer
                    WHERE NoSiri = %s
                """, [no_siri])
                officer_data = cursor.fetchone()

            if officer_data:
                # Check if NoSiri already exists in the officer table
                current_no_siri = officer_data[0]  # The NoSiri from temp_officer (e.g., AM001)
                unique_no_siri = current_no_siri

                while True:
                    with connection.cursor() as cursor:
                        # Check if the NoSiri already exists in the officer table
                        cursor.execute("""
                            SELECT COUNT(*) FROM officer WHERE NoSiri = %s
                        """, [unique_no_siri])
                        result = cursor.fetchone()

                    if result[0] == 0:
                        # NoSiri is unique, proceed with this value
                        break
                    else:
                        # Increment the NoSiri (e.g., AM001 -> AM002)
                        prefix = unique_no_siri[:2]  # 'AM'
                        number = int(unique_no_siri[2:]) + 1  # Increment the number part
                        unique_no_siri = f"{prefix}{str(number).zfill(3)}"  # AM002, AM003, etc.
                        print(unique_no_siri)

                print("Unique NoSiri found:", unique_no_siri)

                # Insert officer data into the 'officer' table with the unique NoSiri
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO officer (NoSiri, Password, Nama, NoKP, Jawatan, Bahagian, Email, Profile, Sign, KadKuasa, TarikhKeluar, Status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURDATE(), 1)
                    """, [
                        unique_no_siri, officer_data[1], officer_data[2], officer_data[3],
                        officer_data[4], officer_data[5], officer_data[6], officer_data[7],
                        officer_data[8], kadkuasa_file.read()
                    ])

                # Delete the record from temp_officer
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM temp_officer WHERE NoSiri = %s", [no_siri])

                # Retry sending the confirmation email up to 3 times if it fails
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        send_mail(
                            'Registration Approved',
                            f'Hello {officer_data[2]},\nYour registration was successful. Here is your information:\n'
                            f'NoSiri: {unique_no_siri}\nPassword: {officer_data[1]}\nNama: {officer_data[2]}\nNoKP: {officer_data[3]}\n'
                            f'Jawatan: {officer_data[4]}\nBahagian: {officer_data[5]}\n',
                            'admin@example.com',
                            [officer_data[6]],
                            fail_silently=False,
                        )
                        break  # Exit the loop if email is sent successfully
                    except Exception as e:
                        print(f"Attempt {attempt + 1} failed: {e}")
                        time.sleep(5)  # Wait for 5 seconds before retrying

                # Redirect after success
                return redirect('data')

    return render(request, '5extend_approve.html')



from django.core.mail import send_mail
from django.db import connection

from django.core.mail import send_mail
from django.db import connection

from django.core.mail import send_mail
from django.db import connection
import time

def decline_action(request, no_siri):
    print("Before")
    if request.method == "POST":
        print("After")
        # Get the reason from the long text input
        rejection_reason = request.POST.get('rejection_reason')

        # Check if rejection_reason exists
        if not rejection_reason:
            return render(request, '5extend_approve.html', {
                'error': 'Reason for rejection is required.',
                'NoSiri': no_siri,
                # Add other context data as needed
            })

        with connection.cursor() as cursor:
            # Fetch officer data from temp_officer
            cursor.execute("""
                SELECT NoSiri, Password, Nama, NoKP, Jawatan, Bahagian, Email, Profile, Sign, Stat
                FROM temp_officer
                WHERE NoSiri = %s
            """, [no_siri])
            officer_data = cursor.fetchone()

        if officer_data:
            # Retry sending the email up to 3 times if it fails
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    send_mail(
                        'Registration Rejected',
                        f'Dear {officer_data[2]},\n\nWe regret to inform you that your registration has been rejected.\n\n'
                        f'Here are your details:\n\n'
                        f'NoSiri: {officer_data[0]}\n'
                        f'Nama: {officer_data[2]}\n'
                        f'NoKP: {officer_data[3]}\n'
                        f'Jawatan: {officer_data[4]}\n'
                        f'Bahagian: {officer_data[5]}\n\n'
                        f'Reason for rejection: {rejection_reason}\n\n'
                        'Best regards,\nAdmin Team',
                        'admin@example.com',
                        [officer_data[6]],  # Officer's email
                        fail_silently=False,
                    )
                    break  # Exit the loop if email is sent successfully
                except Exception as e:
                    print(f"Attempt {attempt + 1} failed: {e}")
                    time.sleep(5)  # Wait for 5 seconds before retrying

            # Update the Stat field to 'Rejected'
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE temp_officer
                    SET Stat = 'Rejected'
                    WHERE NoSiri = %s
                """, [no_siri])

        # Redirect the admin back to the approval page
        return redirect('data')

    return render(request, '5extend_approve.html')




def update(request, no_siri):
    if request.method == 'POST':
        # Fetch form data
        nama = request.POST.get('nama')
        bahagian = request.POST.get('link')
        jawatan = request.POST.get('jawatan')
        status = request.POST.get('status')

        # Handle file uploads
        profile_img = request.FILES.get('profile_img')
        kad_kuasa = request.FILES.get('kad_kuasa')
        
        # Handle Profile Image
        profile_img_data = None
        if profile_img:
            profile_file = ContentFile(profile_img.read())
            profile_img_data = base64.b64encode(profile_file.read()).decode('utf-8')
        else:
            # Fetch the existing image if no new image is uploaded
            with connections['default'].cursor() as cursor:
                cursor.execute("""SELECT Profile FROM officer WHERE NoSiri = %s""", [no_siri])
                result = cursor.fetchone()
                profile_img_data = result[0] if result else None

        # Handle Kad Kuasa PDF
        kad_kuasa_data = None
        if kad_kuasa:
            kad_kuasa_data = kad_kuasa.read()

        # Update the officer data
        with connections['default'].cursor() as cursor:
            cursor.execute("""
                UPDATE officer
                SET Nama = %s, Bahagian = %s, Jawatan = %s, Status = %s, Profile = %s, KadKuasa = %s
                WHERE NoSiri = %s
            """, [nama, bahagian, jawatan, status, profile_img_data, kad_kuasa_data, no_siri])

        messages.success(request, "Officer data updated successfully.")
        return redirect('data')

    # GET request - fetch existing data
    with connections['default'].cursor() as cursor:
        cursor.execute("""
            SELECT NoSiri, Nama, Bahagian, Jawatan, Status, Profile, KadKuasa
            FROM officer
            WHERE NoSiri = %s
        """, [no_siri])
        officer = cursor.fetchone()

    # Convert binary image data to base64 for rendering in HTML
    profile_base64 = f"data:image/jpeg;base64,{officer[5].decode('utf-8')}" if officer[5] else None

    context = {
        'officer': {
            'NoSiri': officer[0],
            'Nama': officer[1],
            'Bahagian': officer[2],
            'Jawatan': officer[3],
            'Status': officer[4],
            'Profile': profile_base64,  # Use base64 encoded string in template
            'KadKuasa': officer[6]  # Include Kad Kuasa data if needed
        }
    }

    return render(request, "6updateData.html", context)



def pdfkadkuasa(request):
    no_siri = request.session.get('NoSiri')
    if not no_siri:
        return redirect('officer_login')

    with connections['default'].cursor() as cursor:
        cursor.execute("""
            SELECT KadKuasa
            FROM officer
            WHERE NoSiri = %s
        """, [no_siri])
        officer = cursor.fetchone()

    if officer and officer[0]:
        response = HttpResponse(officer[0], content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="KadKuasa.pdf"'  # Display inline
        return response

    return HttpResponse("No Kad Kuasa available", status=404)

def user_authorized(request):
    context = {}

    # Extract NoSiri from query parameters
    no_siri = request.GET.get('NoSiri')
    if not no_siri:
        context['error_message'] = 'NoSiri is required.'
        return render(request, "7UserAuthorized.html", context)

    if request.method == 'POST':
        nokp = request.POST.get('NoKP')
        siri = request.POST.get('SIRI')

        with connections['default'].cursor() as cursor:
            # Fetch kadLink based on SIRI and NoKP from perm_officer_db
            cursor.execute("""
                SELECT kadLink
                FROM perm_officer_db
                WHERE SIRI = %s AND NoKP = %s
            """, [siri, nokp])
            result = cursor.fetchone()

            if result:
                kad_link = result[0]
                if kad_link:
                    cleaned_kad_link = kad_link.strip()
                    redirect_url = f"https://www.aelb.gov.my/kadkuasa/{cleaned_kad_link}.html"
                    
                    # Insert record into the `record` table
                    cursor.execute("""
                        INSERT INTO record (NoSiri, date, location)
                        VALUES (%s, %s, ST_PointFromText(%s))
                    """, [no_siri, now().date(), 'POINT(0 0)'])  # Replace 'POINT(0 0)' with actual location if available

                    return redirect(redirect_url)
                else:
                    context['error_message'] = 'Invalid kadLink.'
            else:
                context['error_message'] = 'Invalid SIRI or NoKP.'

    return render(request, "7UserAuthorized.html", context)


import base64

def profile_image_temp(request, no_siri):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT Profile
            FROM temp_officer
            WHERE NoSiri = %s
        """, [no_siri])
        result = cursor.fetchone()
    
    if result and result[0]:
        profile_image_data = result[0]

        # Set proper content type based on the binary data
        if profile_image_data.startswith(b'\xFF\xD8\xFF'):
            content_type = 'image/jpeg'
        elif profile_image_data.startswith(b'\x89PNG'):
            content_type = 'image/png'
        else:
            content_type = 'application/octet-stream'

        return HttpResponse(profile_image_data, content_type=content_type)

    raise Http404("Profile image not found")

#approve

def profile_image(request, no_siri):
    with connections['default'].cursor() as cursor:
        cursor.execute("SELECT Profile FROM officer WHERE NoSiri = %s", [no_siri])
        result = cursor.fetchone()

    if result and result[0]:
        profile_image_data = result[0]

        # Check if the image is JPEG or PNG by inspecting the file's magic numbers
        if profile_image_data.startswith(b'\xFF\xD8\xFF'):
            content_type = 'image/jpeg'  # JPEG
        elif profile_image_data.startswith(b'\x89PNG'):
            content_type = 'image/png'   # PNG
        else:
            content_type = 'application/octet-stream'  # Fallback

        return HttpResponse(profile_image_data, content_type=content_type)

    # Return a 404 error if no image is found
    return HttpResponse(status=404)


class OfficerListView(APIView):
    def get(self, request):
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("""
                    SELECT NoSiri, Password, Nama, NoKP, Jawatan, TarikhKeluar, Status, KadKuasa, Bahagian, profile
                    FROM officer
                """)
                officers = cursor.fetchall()

            if not officers:
                return Response({'message': 'No officers found'}, status=status.HTTP_404_NOT_FOUND)

            officer_data = [
                {
                    'NoSiri': row[0],
                    'Password': row[1],
                    'Nama': row[2],
                    'NoKP': row[3],
                    'Jawatan': row[4],
                    'TarikhKeluar': row[5],
                    'Status': bool(row[6]),  # Convert tinyint(1) to boolean
                    'KadKuasa': base64.b64encode(row[7]).decode('utf-8') if row[7] else None,  # Encode binary data to base64
                    'Bahagian': row[8],
                    'Profile': base64.b64encode(row[9]).decode('utf-8') if row[9] else None,  # Encode binary data to base64
                }
                for row in officers
            ]

            return Response(officer_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from django.http import HttpResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.conf import settings
import os

from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.db import connection

def download_profile_image(request, no_siri):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT Profile
            FROM temp_officer
            WHERE NoSiri = %s
        """, [no_siri])
        result = cursor.fetchone()

    if result and result[0]:
        response = HttpResponse(result[0], content_type='image/jpeg')
        response['Content-Disposition'] = f'attachment; filename="{no_siri}_profile.jpg"'
        return response

    # Debug message
    print(f"Profile image for {no_siri} not found.")

    # Return a 404 error if the image is not found
    raise Http404("Profile image not found")

def download_sign_image(request, no_siri):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT Sign
            FROM temp_officer
            WHERE NoSiri = %s
        """, [no_siri])
        result = cursor.fetchone()

    if result and result[0]:
        # Determine content type and file extension
        content_type = 'image/jpeg'  # Default to JPEG
        file_extension = 'jpg'  # Default to JPG

        # Check if the image data indicates PNG
        if result[0].startswith(b'\x89PNG'):
            content_type = 'image/png'
            file_extension = 'png'

        response = HttpResponse(result[0], content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{no_siri}_sign.{file_extension}"'
        return response

    # Debug message
    print(f"Sign image for {no_siri} not found.")

    # Return a 404 error if the image is not found
    raise Http404("Sign image not found")


def get_profile_image_path(no_siri):
    # Implement this function based on how you store your images
    # This is a placeholder function
    # Example path: settings.MEDIA_ROOT / 'profiles' / f'{no_siri}_profile.jpg'
    return os.path.join(settings.MEDIA_ROOT, 'profiles', f'{no_siri}_profile.jpg')

def get_sign_image_path(no_siri):
    # Implement this function based on how you store your images
    # This is a placeholder function
    # Example path: settings.MEDIA_ROOT / 'signs' / f'{no_siri}_sign.jpg'
    return os.path.join(settings.MEDIA_ROOT, 'signs', f'{no_siri}_sign.jpg')

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db import connection
import zipfile
import io

def download_images_zip(request, no_siri):
    # Create an in-memory buffer to hold the zip file
    buffer = io.BytesIO()
    
    with zipfile.ZipFile(buffer, 'w') as zip_file:
        # Fetch the profile image
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT Profile
                FROM temp_officer
                WHERE NoSiri = %s
            """, [no_siri])
            result = cursor.fetchone()

        if result and result[0]:
            zip_file.writestr(f'{no_siri}_profile.jpg', result[0])

        # Fetch the sign image
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT Sign
                FROM temp_officer
                WHERE NoSiri = %s
            """, [no_siri])
            result = cursor.fetchone()

        if result and result[0]:
            zip_file.writestr(f'{no_siri}_sign.jpg', result[0])

    # Seek to the beginning of the BytesIO buffer
    buffer.seek(0)

    # Create HTTP response with the zip file
    response = HttpResponse(buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{no_siri}_images.zip"'
    return response

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from django.http import HttpResponse

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from io import BytesIO
from django.http import HttpResponse

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Image
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from io import BytesIO
import datetime
from django.contrib.staticfiles import finders

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Image
from django.contrib.staticfiles import finders
from datetime import datetime
from io import BytesIO
from django.http import HttpResponse

def download_officer_pdf(request):
    # Fetch all officers from the database
    with connections['default'].cursor() as cursor:
        cursor.execute("""
            SELECT NoSiri, Nama, Bahagian, Jawatan, Status
            FROM officer
        """)
        officers = cursor.fetchall()

    # Create a PDF in memory
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []

    # Add header with company logo and report title
    styles = getSampleStyleSheet()

    # Add the logo
    logo_path = finders.find('images.png')  # Correctly locate the logo

    if not logo_path:
        # Handle case where logo isn't found
        return HttpResponse("Logo not found", status=404)

    logo = Image(logo_path, width=2.1 * inch, height=1.2 * inch)
    
    current_date = datetime.now().strftime("%d/%m/%Y")

    # Define the title and date as Paragraph objects
    title = Paragraph("<b>Jabatan Tenaga Atom</b><br/><b>Report Data Pegawai</b>", styles['Title'])
    date = Paragraph(f"<b>Tarikh Dikeluarkan: {current_date}</b>", styles['Normal'])

    # Create a table for the header with 2 columns (one for the logo and one for text)
    header_data = [[logo, title],  # Row for logo and title
                   ['', date]]     # Row for the date (aligned below the title)

    # Create the Table object
    header_table = Table(header_data, colWidths=[1.5 * inch, 4.5 * inch])

    # Add styles to control alignment and padding within the table
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertically align all cells to middle
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),       # Align the logo to the left
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),     # Align the title to the center
        ('ALIGN', (1, 1), (1, 1), 'RIGHT'),      # Align the date to the right
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12), # Add some padding below the text
        ('SPAN', (0, 0), (0, 1)),                # Span the logo over two rows
    ]))

    elements.append(header_table)
    elements.append(Paragraph('<hr/>', styles['Normal']))

    # Table data including headers
    table_data = [['NoSiri', 'Nama', 'Bahagian', 'Jawatan', 'Status']]
    for officer in officers:
        # Break text into multiple lines if it’s too long
        no_siri, nama, bahagian, jawatan, status = officer
        status_text = "Active" if status else "Inactive"
        row = [
            no_siri, 
            Paragraph(nama, styles['BodyText']), 
            Paragraph(bahagian, styles['BodyText']),
            Paragraph(jawatan, styles['BodyText']),
            status_text
        ]
        table_data.append(row)

    # Create officer data table with style
    officer_table = Table(table_data, colWidths=[1.2 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch, 1 * inch])
    officer_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),  # Header row font size
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(officer_table)

    # Add total number of officers
    total_officers = len(officers)
    elements.append(Paragraph(f"<br/><br/>Pegawai: {total_officers} orang", styles['Normal']))

    # Build the PDF
    pdf.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="officer_data_report.pdf"'
    return response

#-----------------------------API REST--------------------------------------------------
# views.py

class OfficerListView(APIView):
    def get(self, request):
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("""
                    SELECT NoSiri, Password, Nama, NoKP, Jawatan, TarikhKeluar, Status, KadKuasa, Bahagian, profile
                    FROM officer
                """)
                officers = cursor.fetchall()

            if not officers:
                return Response({'message': 'No officers found'}, status=status.HTTP_404_NOT_FOUND)

            officer_data = [
                {
                    'NoSiri': row[0],
                    'Password': row[1],
                    'Nama': row[2],
                    'NoKP': row[3],
                    'Jawatan': row[4],
                    'TarikhKeluar': row[5],
                    'Status': bool(row[6]),  # Convert tinyint(1) to boolean
                    'KadKuasa': base64.b64encode(row[7]).decode('utf-8') if row[7] else None,  # Encode binary data to base64
                    'Bahagian': row[8],
                    'Profile': base64.b64encode(row[9]).decode('utf-8') if row[9] else None,  # Encode binary data to base64
                }
                for row in officers
            ]

            return Response(officer_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import OfficerLoginSerializer

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

def officer_login(request):
    message = ''
    if request.method == 'POST':
        no_siri = request.POST.get('NoSiri')
        password = request.POST.get('password')

        with connections['default'].cursor() as cursor:
            cursor.execute("SELECT * FROM officer WHERE NoSiri = %s AND Password = %s", [no_siri, password])
            officer = cursor.fetchone()

            if officer:
                request.session['NoSiri'] = no_siri
                return redirect('user_data')  # Redirect to officer's data page
            else:
                message = 'Invalid NoSiri or password.'
    return render(request, "1UserLoginPage.html", {'message':message})


import base64
from django.core.files.base import ContentFile
from django.db import connection, IntegrityError

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.shortcuts import render, redirect
import base64
from django.db import connection

def user_sign_up(request):
    if request.method == 'POST':
        # Get form data
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        nokp = request.POST.get('NoKP')
        profile = request.FILES.get('Profile')
        sign = request.FILES.get('Sign')

        # Validate email domain
        if email != 'danish25122004@gmail.com' and not email.endswith('@aelb.gov.my'):
            return render(request, '1UserSignUpPage.html', {'errorEmail': 'Email must end with \'@aelb.gov.my\'.'})

        # Check if passwords match
        if password != confirm_password:
            return render(request, '1UserSignUpPage.html', {'errorPass': 'Kata laluan tidak sepadan.'})

        # Check if NoKP exists in perm_officer_db
        officer_data = check_nokp_in_perm_officer(nokp)
        if not officer_data:
            return render(request, '1UserSignUpPage.html', {'errorKP': 'NoKP not found.'})

        # Insert data into TempOfficer table
        try:
            # Convert images to base64
            profile_base64 = None
            sign_base64 = None

            if profile:
                profile_file = ContentFile(profile.read())
                profile_base64 = base64.b64encode(profile_file.read()).decode('utf-8')

            if sign:
                sign_file = ContentFile(sign.read())
                sign_base64 = base64.b64encode(sign_file.read()).decode('utf-8')

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO temp_officer (NoSiri, Password, Nama, NoKP, Jawatan, Bahagian, Email, Profile, Sign, Stat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    officer_data['Siri'], 
                    password, 
                    officer_data['NamaPegawai'], 
                    nokp, 
                    officer_data['Jawatan'], 
                    officer_data['KadLink'], 
                    email, 
                    profile_base64, 
                    sign_base64, 
                    'Pending'
                ])
            # Redirect to the success page or the login page
            return redirect('officer_login')  # Change 'success_page' to your actual success redirect page

        except IntegrityError:
            # Handle NoKP already exists in temp_officer or officer tables
            return render(request, '1UserSignUpPage.html', {'errorKP': 'NoKP already exists in the system.'})
        except Exception as e:
            # Generic error handling
            print('error : ', e)
            return render(request, '1UserSignUpPage.html', {'error404': 'Something went wrong'})

    return render(request, '1UserSignUpPage.html')

def check_nokp_in_perm_officer(nokp):
    """
    Check if the NoKP exists in the perm_officer_db table.
    Returns the officer's data if found, otherwise returns None.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM perm_officer_db WHERE NoKP = %s", [nokp])
        row = cursor.fetchone()
    if row:
        return {
            'Siri': row[0],
            'NamaPegawai': row[1],  # Adjust the index based on your actual column order
            'Jawatan': row[3],
            'KadLink': row[4]
        }
    return None

from django.urls import reverse

def user_data(request):
    no_siri = request.session.get('NoSiri')
    if not no_siri:
        return redirect('officer_login')  # Redirect to login page if not authenticated

    with connections['default'].cursor() as cursor:
        cursor.execute("""
            SELECT NoSiri, Nama, Bahagian, Jawatan, Status, Profile, KadKuasa
            FROM officer
            WHERE NoSiri = %s
        """, [no_siri])
        officer = cursor.fetchone()

    if officer:
        # Generate URL for the profile image view
        profile_url = f"data:image/jpeg;base64,{officer[5].decode('utf-8')}" if officer[5] else None

        # Convert KadKuasa (PNG) to base64 for rendering in HTML
        kad_kuasa_base64 = f"data:image/png;base64,{base64.b64encode(officer[6]).decode('utf-8')}" if officer[6] else None

        # Generate QR code with NoSiri included in the URL
        qr_data = request.build_absolute_uri(f'{officer[2]}')
        qr = qrcode.make(qr_data)
        qr_buffer = BytesIO()
        qr.save(qr_buffer, format='PNG')
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')

        context = {
            'officer': {
                'NoSiri': officer[0],
                'Nama': officer[1],
                'Bahagian': officer[2],
                'Jawatan': officer[3],
                'Status': officer[4],
                'ProfileURL': profile_url,  # Use the URL for Profile image
                'KadKuasa': kad_kuasa_base64,  # Use base64 encoded string for Kad Kuasa (PNG)
                'QRCode': qr_base64  # Use base64 encoded string for QR code
            }
        }
    else:
        context = {
            'error': 'Officer not found.'
        }

    return render(request, "2UserDataPage.html", context)


from django.http import HttpResponse

def kadkuasa_image(request):
    no_siri = request.session.get('NoSiri')
    if not no_siri:
        return redirect('officer_login')

    with connections['default'].cursor() as cursor:
        cursor.execute("""
            SELECT KadKuasa
            FROM officer
            WHERE NoSiri = %s
        """, [no_siri])
        officer = cursor.fetchone()

    if officer and officer[0]:
        # Return the KadKuasa PNG image directly
        response = HttpResponse(officer[0], content_type='image/png')
        response['Content-Disposition'] = 'inline; filename="KadKuasa.png"'  # Display inline
        return response

    return HttpResponse("No Kad Kuasa available", status=404)
