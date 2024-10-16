import io
import fitz
import logging
import qrcode
import base64
import os
import imghdr
import time

from django.db import connections, connection
from django.core import signing
from django.utils import timezone, http
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import datetime, timedelta

#email
def h(request):
    return render(request, "h.html")

def d(request):
    return render(request, "d.html")

def k(request):
    return render(request, 'k.html', status=404)

def p(request):
    return render(request, 'p.html', status=500)

def login(request):
    message = ''
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SELECT * FROM admin WHERE user = %s AND pasword = %s", [username, password])
                user = cursor.fetchone()

                if user:
                    request.session['username'] = username
                    return redirect('data')
                else:
                    message = 'Invalid username or password.'
        except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')
    return render(request, "1loginPage.html", {'message' : message})



def forgot(request):
    message = ''  # Initialize message variable
    if request.method == 'POST':
        no_siri = request.POST.get('NoSiri')
        email = request.POST.get('Email')

        try:
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
                        f'Sila klik pautan ini untuk menetapkan kata laluan baru anda:\n{reset_link}',
                        'noreply@aelb.gov.my', 
                        [email],
                        fail_silently=False,
                    )
                    message = "We've send you an email"
                else:
                    message = "Invalid Email"
            else:
                message = "No. Siri not found"
            
        except Exception as e:
            print('error: ', e)
            return render(request, 'h.html')

    return render(request, "10UserForgot.html", {'message': message})


def reset_password(request, token):
    message = ''
    no_siri = check_token(token)  # Validate the token and get NoSiri

    if no_siri is None:
        message = "Pautan reset tidak sah atau telah tamat tempoh."
        return redirect('forgot')

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        try:
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
        except Exception as e:
            print('error: ', e)
            return render(request, 'h.html')

    return render(request, "11ResetPass.html", {'message' : message})



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
            return None 
        return data['NoSiri']
    except signing.BadSignature:
        return None 


def data(request, filter_by='Nama', query=''):
    try:
        with connection.cursor() as cursor:
            query_sql = f"""
                SELECT NoSiri, Nama, Bahagian, Jawatan, Status, Profile
                FROM officer
                WHERE {filter_by} LIKE %s
            """

            cursor.execute(query_sql, [f'%{query}%'])
            officers_raw = cursor.fetchall()  

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

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT Stat
                FROM temp_officer
                WHERE Stat = 'Pending'
            """)
            has_pending = cursor.fetchall()

        # Pass the processed data to the template
        context = {
            'officers': officers,
            'has_pending': has_pending
        }
    except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')
    return render(request, '2dataPage.html', context)

def report(request):
    try:
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
    except Exception as e:
        print('error: ', e)
        return render(request, 'd.html')
    return render(request, "3reportPage.html", context)



def personal(request, no_siri):
    try:
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
            'raw': daily_counts,
            'dates': dates,  
            'counts': counts, 
            'NoSiri': officer_data[0],
            'Nama': officer_data[1],
            'NoKP': officer_data[2],
            'Jawatan': officer_data[3],
            'Bahagian': officer_data[4],
            'Email': officer_data[5],
            'Status': officer_data[6],
            'Profile': f"data:image/jpeg;base64,{officer_data[7].decode('utf-8')}",
            'month_name': today.strftime('%B') 
        }
    except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')
    return render(request, "4reportPersonalPage.html", context)


def approve(request):
    pending_officers = []
    rejected_officers = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT NoSiri, Nama, Profile
                FROM temp_officer
                WHERE Stat = 'Pending'
            """)
            officersPending = cursor.fetchall()
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT NoSiri, Nama, Profile
                FROM temp_officer
                WHERE Stat = 'Rejected'
            """)
            officersRejected = cursor.fetchall()

            # Loop through officers and convert their profile image to base64
            for officer in officersPending:
                if officer[2]:  # Check if profile image exists
                    profile_base64 = f"data:image/jpeg;base64,{officer[2].decode('utf-8')}"
                else:
                    profile_base64 = None

                pending_officers.append({
                    'NoSiri': officer[0],
                    'Nama': officer[1],
                    'Profile': profile_base64,
                })
            for officer in officersRejected:
                if officer[2]:  # Check if profile image exists
                    profile_base64 = f"data:image/jpeg;base64,{officer[2].decode('utf-8')}"
                else:
                    profile_base64 = None

                rejected_officers.append({
                    'NoSiri': officer[0],
                    'Nama': officer[1],
                    'Profile': profile_base64,
                })
    except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')
    return render(request, "5approveData.html", {'pending_officers': pending_officers, 'rejected_officers': rejected_officers})

def delete_officer(request, no_siri):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM temp_officer
                WHERE NoSiri = %s
            """, [no_siri])
        return redirect('approve')
    except Exception as e:
        print('error: ', e)
        return render(request, 'd.html')

def extend_approve(request, no_siri):
    try:
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
    except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')
    

def approve_action(request, no_siri):
    if request.method == "POST":
        # Get the PDF file (Kad Kuasa)
        kadkuasa_file = request.FILES.get('kadkuasa')
        kadkuasaBelakang_file = request.FILES.get('kadkuasaBelakang')

        try:
            if kadkuasa_file and kadkuasaBelakang_file:
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
                            break
                        else:
                            return redirect('approve', {'message': "This officer is already exist. You can't approve this process"})

                    print("Unique NoSiri found:", unique_no_siri)

                    # Insert officer data into the 'officer' table with the unique NoSiri
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO officer (NoSiri, Password, Nama, NoKP, Jawatan, Bahagian, Email, Profile, Sign, KadKuasa, KadKuasaBelakang, TarikhKeluar, Status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURDATE(), 1)
                        """, [
                            unique_no_siri, officer_data[1], officer_data[2], officer_data[3],
                            officer_data[4], officer_data[5], officer_data[6], officer_data[7],
                            officer_data[8], kadkuasa_file.read(), kadkuasaBelakang_file.read()
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
                                f'Jawatan: {officer_data[4]}\nLink Direktori Kakitangan: https://www.aelb.gov.my/kadkuasa/{officer_data[5]}.html\n',
                                'admin@aelb.gov.my',
                                [officer_data[6]],
                                fail_silently=False,
                            )
                            break  # Exit the loop if email is sent successfully
                        except Exception as e:
                            print(f"Attempt {attempt + 1} failed: {e}")
                            time.sleep(5)  # Wait for 5 seconds before retrying

                    # Redirect after success
                    return redirect('data')
        except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')
    return render(request, '5extend_approve.html')


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

        try:
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
                            f'Jawatan: {officer_data[4]}\n\n'
                            f'Reason for rejection: {rejection_reason}\n\n'
                            'Best regards,\nUrus Setia Kadkuasa',
                            'admin@aelb.gov.my',
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
        except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')

    return render(request, '5extend_approve.html')




def update(request, no_siri):
    try:
        if request.method == 'POST':
            # Fetch form data
            nama = request.POST.get('nama')
            bahagian = request.POST.get('link')
            jawatan = request.POST.get('jawatan')
            status = request.POST.get('status')

            # Handle file uploads
            profile_img = request.FILES.get('profile_img')
            kad_kuasa = request.FILES.get('kad_kuasa')
            kad_kuasa_belakang = request.FILES.get('kad_kuasa_belakang')

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
            else:
                # Fetch the existing image if no new image is uploaded
                with connections['default'].cursor() as cursor:
                    cursor.execute("""SELECT KadKuasa FROM officer WHERE NoSiri = %s""", [no_siri])
                    result = cursor.fetchone()
                    kad_kuasa_data = result[0] if result else None

            kad_kuasa_belakang_data = None
            if kad_kuasa:
                kad_kuasa_belakang_data = kad_kuasa_belakang.read()
            else:
                # Fetch the existing image if no new image is uploaded
                with connections['default'].cursor() as cursor:
                    cursor.execute("""SELECT KadKuasaBelakang FROM officer WHERE NoSiri = %s""", [no_siri])
                    result = cursor.fetchone()
                    kad_kuasa_belakang_data = result[0] if result else None

            # Update the officer data
            with connections['default'].cursor() as cursor:
                cursor.execute("""
                    UPDATE officer
                    SET Nama = %s, Bahagian = %s, Jawatan = %s, Status = %s, Profile = %s, KadKuasa = %s, KadKuasaBelakang = %s
                    WHERE NoSiri = %s
                """, [nama, bahagian, jawatan, status, profile_img_data, kad_kuasa_data, kad_kuasa_belakang_data, no_siri])

            messages.success(request, "Officer data updated successfully.")
            return redirect('data')

        # GET request - fetch existing data
        with connections['default'].cursor() as cursor:
            cursor.execute("""
                SELECT NoSiri, Nama, Bahagian, Jawatan, Status, Profile, KadKuasa, KadKuasaBelakang
                FROM officer
                WHERE NoSiri = %s
            """, [no_siri])
            officer = cursor.fetchone()

        # Convert binary image data to base64 for rendering in HTML
        profile_base64 = f"data:image/jpeg;base64,{officer[5].decode('utf-8')}" if officer[5] else None
        kad_kuasa_base64 = f"data:image/png;base64,{base64.b64encode(officer[6]).decode('utf-8')}" if officer[6] else None
        kad_kuasa_belakang_base64 = f"data:image/png;base64,{base64.b64encode(officer[7]).decode('utf-8')}" if officer[7] else None

        context = {
            'officer': {
                'NoSiri': officer[0],
                'Nama': officer[1],
                'Bahagian': officer[2],
                'Jawatan': officer[3],
                'Status': officer[4],
                'Profile': profile_base64,  # Use base64 encoded string in template
                'KadKuasa': kad_kuasa_base64,
                'KadKuasaBelakang': kad_kuasa_belakang_base64,  # Include Kad Kuasa data if needed
            }
        }
    except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')
    return render(request, "6updateData.html", context)

#download

from datetime import datetime
from django.shortcuts import render, redirect
from django.db import connections

def user_authorized(request, no_siri):
    context = {}

    try:
        if not no_siri:
            context['error_message'] = 'NoSiri is required.'
            return render(request, "7UserAuthorized.html", context)

        with connections['default'].cursor() as cursor:
            # Fetch kadLink based on SIRI and NoKP from perm_officer_db
            cursor.execute("""
                SELECT kadLink
                FROM perm_officer_db
                WHERE SIRI = %s 
            """, [no_siri])
            result = cursor.fetchone()
            print(f"Query result: {result}")  # Debugging statement
            if result:
                kad_link = result[0]
                print(f"Fetched kadLink: {kad_link}")  # Debugging statement
                if kad_link:
                    cleaned_kad_link = kad_link.strip()
                    redirect_url = f"https://www.aelb.gov.my/v2/kadkuasa/{cleaned_kad_link}.html"
                    print(f"Redirect URL: {redirect_url}")  # Debugging statement
                    # Insert record into the `record` table
                    cursor.execute("""
                        INSERT INTO record (NoSiri, date, location)
                        VALUES (%s, %s, ST_PointFromText(%s))
                    """, [no_siri, datetime.now().date(), 'POINT(0 0)'])  # Replace 'POINT(0 0)' with actual location if available
                    print(f"Inserted record - NoSiri: {no_siri}, Date: {datetime.now().date()}, Location: POINT(0 0)")  # Debugging statement
                    return redirect(redirect_url)
                else:
                    context['error_message'] = 'Invalid kadLink.'
                    print("Error: Invalid kadLink.")  # Debugging statement


    except Exception as e:
        print('Error: ', e)  # Debugging statement for exceptions
        return render(request, 'h.html')

    return render(request, "7UserAuthorized.html", context)



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

from django.db import connection
import zipfile
import io

def download_images_zip(request, no_siri):
    # Create an in-memory buffer to hold the zip file
    buffer = io.BytesIO()
    
    try:
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
    except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from io import BytesIO

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

def download_officer_pdf(request):
    try:
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
    except Exception as e:
            print('error: ', e)
            return render(request, 'd.html')

#-----------------------------API REST--------------------------------------------------
# views.py
        
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connections
import base64

class OfficerRecordListView(APIView):
    def get(self, request):
        try:
            with connections['default'].cursor() as cursor:
                # Fetch all officers
                cursor.execute("""
                    SELECT NoSiri, Password, Nama, NoKP, Jawatan, TarikhKeluar, Status, KadKuasa, Bahagian, profile
                    FROM officer
                """)
                officers = cursor.fetchall()

                # Fetch all records
                cursor.execute("""
                    SELECT NoSiri, date, location
                    FROM record
                """)
                records = cursor.fetchall()

            if not officers and not records:
                return Response({'message': 'No data found'}, status=status.HTTP_404_NOT_FOUND)

            officer_data = [
                {
                    'NoSiri': row[0],
                    'Password': row[1],
                    'Nama': row[2],
                    'NoKP': row[3],
                    'Jawatan': row[4],
                    'TarikhKeluar': row[5],
                    'Status': bool(row[6]),
                    'KadKuasa': base64.b64encode(row[7]).decode('utf-8') if row[7] else None,
                    'Bahagian': row[8],
                    'Profile': base64.b64encode(row[9]).decode('utf-8') if row[9] else None,
                }
                for row in officers
            ]

            record_data = [
                {
                    'NoSiri': row[0],
                    'date': row[1],
                    'location': row[2]
                }
                for row in records
            ]

            response_data = {
                'officers': officer_data,
                'records': record_data
            }

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OfficerRecordDetailView(APIView):
    def get(self, request, no_siri):
        try:
            with connections['default'].cursor() as cursor:
                # Fetch specific officer
                cursor.execute("""
                    SELECT NoSiri, Password, Nama, NoKP, Jawatan, TarikhKeluar, Status, KadKuasa, Bahagian, profile
                    FROM officer
                    WHERE NoSiri = %s
                """, [no_siri])
                officer = cursor.fetchone()

                # Fetch records for the specific officer
                cursor.execute("""
                    SELECT NoSiri, date, location
                    FROM record
                    WHERE NoSiri = %s
                """, [no_siri])
                records = cursor.fetchall()

            if not officer:
                return Response({'message': 'Officer not found'}, status=status.HTTP_404_NOT_FOUND)

            officer_data = {
                'NoSiri': officer[0],
                'Password': officer[1],
                'Nama': officer[2],
                'NoKP': officer[3],
                'Jawatan': officer[4],
                'TarikhKeluar': officer[5],
                'Status': bool(officer[6]),
                'KadKuasa': base64.b64encode(officer[7]).decode('utf-8') if officer[7] else None,
                'Bahagian': officer[8],
                'Profile': base64.b64encode(officer[9]).decode('utf-8') if officer[9] else None,
            }

            record_data = [
                {
                    'NoSiri': row[0],
                    'date': row[1],
                    'location': row[2]
                }
                for row in records
            ]

            response_data = {
                'officer': officer_data,
                'records': record_data
            }

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.files.base import ContentFile
import base64
from django.db import transaction
from django.db import IntegrityError

class UserSignUpView(APIView):
    @transaction.atomic
    def post(self, request):
        # Get form data
        email = request.data.get('email')
        password = request.data.get('password')
        confirm_password = request.data.get('confirm_password')
        nokp = request.data.get('NoKP')
        profile_base64 = request.data.get('Profile')
        sign_base64 = request.data.get('Sign')

        print(f"Email: {email}, NoKP: {nokp}")

        # Validate email domain
        if email != 'danish25122004@gmail.com' and not email.endswith('@aelb.gov.my'):
            print("Invalid email domain.")
            return Response({'error': 'Email must end with \'@aelb.gov.my\''}, status=400)

        # Check if passwords match
        if password != confirm_password:
            print("Passwords do not match.")
            return Response({'error': 'Kata laluan tidak sepadan.'}, status=400)

        # Check if NoKP exists in perm_officer_db
        officer_data = check_nokp_in_perm_officer(nokp)
        print(f"Officer data from perm_officer_db: {officer_data}")

        if not officer_data:
            print("NoKP not found in perm_officer_db.")
            return Response({'error': 'NoKP not found.'}, status=400)

        # Check for duplicate NoKP in temp_officer and officer
        dupe_officer_data = check_nokp_dupe(nokp)
        print(f"Duplicate check result: {dupe_officer_data}")

        if not dupe_officer_data:
            print("Duplicate NoKP found.")
            return Response({'error': 'NoKP already exists in the system.'}, status=400)

        # Proceed to insert data into TempOfficer table
        print("Inserting new officer into temp_officer.")
        try:
            # Decode base64 images
            profile_image = None
            sign_image = None

            if profile_base64:
                profile_image = profile_base64

            if sign_base64:
                sign_image = sign_base64

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
                    profile_image, 
                    sign_image, 
                    'Pending'
                ])
            return Response({'message': 'User  signed up successfully'}, status=201)

        except IntegrityError as e:
            return Response({'error': 'NoKP already exists in the system.'}, status=400)
        except Exception as e:
            return Response({'error': 'An error occurred'}, status=500)

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

class OfficerLoginAPI(APIView):
    def post(self, request):
        no_siri = request.data.get('NoSiri')
        password = request.data.get('password')

        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SELECT * FROM officer WHERE NoSiri = %s AND Password = %s", [no_siri, password])
                officer = cursor.fetchone()

                if officer:
                    request.session['NoSiri'] = no_siri
                    return Response({'message': 'Login successful'}, status=HTTP_200_OK)
                else:
                    return Response({'error': 'Invalid NoSiri or password.'}, status=HTTP_401_UNAUTHORIZED)
        except Exception as e:
            print('error: ', e)
            return Response({'error': 'An error occurred'}, status=500)

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
import base64
import qrcode
from io import BytesIO
from django.http import HttpResponse

class OfficerDataView(APIView):
    def get(self, request, no_siri):
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("""
                    SELECT NoSiri, Nama, NoKP, Jawatan, Bahagian, Email, Profile, KadKuasa, Status, KadKuasaBelakang, TarikhKeluar
                    FROM officer
                    WHERE NoSiri = %s
                """, [no_siri])
                officer = cursor.fetchone()

            if officer:
                # Generate URL for the profile image view
                profile_url = f"data:image/jpeg;base64,{officer[6].decode('utf-8')}" if officer[6] else None

                # Convert KadKuasa (PNG) to base64 for rendering in HTML
                kad_kuasa_base64 = f"data:image/png;base64,{base64.b64encode(officer[7]).decode('utf-8')}" if officer[7] else None

                kad_kuasa_Belakang_base64 = f"data:image/png;base64,{base64.b64encode(officer[9]).decode('utf-8')}" if officer[9] else None

                # Generate QR code with NoSiri included in the URL
                qr_data = f"{officer[4]}"
                qr = qrcode.make(qr_data)
                qr_buffer = BytesIO()
                qr.save(qr_buffer, format='PNG')
                qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')

                context = {
                    'officer': {
                        'NoSiri': officer[0],
                        'Nama': officer[1],
                        'NoKP': officer[2],
                        'Jawatan': officer[3],
                        'Bahagian': officer[4],
                        'Email': officer[5],
                        'ProfileURL': profile_url,
                        'KadKuasa': kad_kuasa_base64,
                        'QRCode': qr_base64,
                        'Status': officer[8],
                        'KadKuasaBelakang': kad_kuasa_Belakang_base64,
                        "TarikhKeluar" : officer[10],
                    }
                }
                return Response(context)
            else:
                return Response({'error': 'Officer not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print('error: ', e)
            return Response({'error': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.db import connection
from datetime import datetime, timedelta
import base64

class RecordView(APIView):
    def get(self, request, no_siri):
        try:
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
                    return Response({"error": "Officer not found"}, status=status.HTTP_404_NOT_FOUND)

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
                'raw': daily_counts,
                'dates': dates,  
                'counts': counts, 
                'NoSiri': officer_data[0],
                'Nama': officer_data[1],
                'NoKP': officer_data[2],
                'Jawatan': officer_data[3],
                'Bahagian': officer_data[4],
                'Email': officer_data[5],
                'Status': officer_data[6],
                'month_name': today.strftime('%B') 
            }
            return Response(context)
        except Exception as e:
            print('error: ', e)
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SELECT * FROM officer WHERE NoSiri = %s AND Password = %s", [no_siri, password])
                officer = cursor.fetchone()

                if officer:
                    request.session['NoSiri'] = no_siri
                    return redirect('user_data')  # Redirect to officer's data page
                else:
                    message = 'Invalid NoSiri or password.'
        except Exception as e:
            print('error: ', e)
            return render(request, 'h.html')
    return render(request, "1UserLoginPage.html", {'message':message})


from django.core.files.base import ContentFile
from django.db import connection, IntegrityError

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.shortcuts import render, redirect
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
        print(officer_data)
        if not officer_data:
            return render(request, '1UserSignUpPage.html', {'errorKP': 'NoKP not found.'})
        
        dupe_officer_data = check_nokp_dupe(nokp)
        if not dupe_officer_data:
            return render(request, '1UserSignUpPage.html', {'errorKP': 'NoKP already exists in the system.'})

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
            print('error: ', e)
            return render(request, 'h.html')

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
            'NamaPegawai': row[1], 
            'Jawatan': row[3],
            'KadLink': row[4]
        }
    return None

def check_nokp_dupe(nokp):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM temp_officer WHERE NoKP = %s", [nokp])
        temp_row = cursor.fetchone()
        print(f"Check in temp_officer, NoKP: {nokp}, result: {temp_row}")
        
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM officer WHERE NoKP = %s", [nokp])
        row = cursor.fetchone()
        print(f"Check in officer, NoKP: {nokp}, result: {row}")

    if not row and not temp_row:
        print(f"NoKP {nokp} does not exist in temp_officer or officer.")
        return {
            'Siri': 'ok'
        }
    
    print(f"NoKP {nokp} already exists in one of the tables.")
    return None


from django.urls import reverse

def user_data(request):
    no_siri = request.session.get('NoSiri')
    if not no_siri:
        return redirect('officer_login')

    try:
        with connections['default'].cursor() as cursor:
            cursor.execute("""
                SELECT NoSiri, Nama, NoKP, Jawatan, Bahagian, Email, Profile, KadKuasa, Status, KadKuasaBelakang
                FROM officer
                WHERE NoSiri = %s
            """, [no_siri])
            officer = cursor.fetchone()

        if officer:
            # Generate URL for the profile image view
            profile_url = f"data:image/jpeg;base64,{officer[6].decode('utf-8')}" if officer[6] else None

            # Convert KadKuasa (PNG) to base64 for rendering in HTML
            kad_kuasa_base64 = f"data:image/png;base64,{base64.b64encode(officer[7]).decode('utf-8')}" if officer[7] else None

            kad_kuasa_Belakang_base64 = f"data:image/png;base64,{base64.b64encode(officer[9]).decode('utf-8')}" if officer[9] else None

            # Generate QR code with NoSiri included in the URL
            qr_data = request.build_absolute_uri(f'{officer[4]}')
            qr = qrcode.make(qr_data)
            qr_buffer = BytesIO()
            qr.save(qr_buffer, format='PNG')
            qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')

            context = {
                'officer': {
                    'NoSiri': officer[0],
                    'Nama': officer[1],
                    'NoKP': officer[2],
                    'Jawatan': officer[3],
                    'Bahagian': officer[4],
                    'Email': officer[5],
                    'ProfileURL': profile_url,
                    'KadKuasa': kad_kuasa_base64,
                    'KadKuasaBelakang': kad_kuasa_Belakang_base64,
                    'QRCode': qr_base64,
                    'Status': officer[8]
                }
            }
        else:
            context = {
                'error': 'Officer not found.'
            }
    except Exception as e:
        print('error: ', e)
        return render(request, 'h.html')

    return render(request, "2UserDataPage.html", context)



def kadkuasa_image(request):
    no_siri = request.session.get('NoSiri')
    if not no_siri:
        return redirect('officer_login')
    try:
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
    except Exception as e:
            print('error: ', e)
            return render(request, 'h.html')

    return HttpResponse("No Kad Kuasa available", status=404)

def officer_logout(request):
    request.session.flush()
    return redirect('officer_login')

#----------------------------------------------------------------Testing----------------------------------------------------------------
'''def user_authorized(request):
    context = {}

    try:
        # Extract NoSiri from query parameters
        no_siri = request.GET.get('NoSiri')
        print(f"Extracted NoSiri: {no_siri}")  # Debugging statement

        if not no_siri:
            context['error_message'] = 'NoSiri is required.'
            return render(request, "7UserAuthorized.html", context)

        if request.method == 'POST':
            nokp = request.POST.get('NoKP')
            siri = request.POST.get('SIRI')
            print(f"Received POST data - NoKP: {nokp}, SIRI: {siri}")  # Debugging statement

            with connections['default'].cursor() as cursor:
                # Fetch kadLink based on SIRI and NoKP from perm_officer_db
                cursor.execute("""
                    SELECT kadLink
                    FROM perm_officer_db
                    WHERE SIRI = %s AND NoKP = %s
                """, [siri, nokp])
                result = cursor.fetchone()
                print(f"Query result: {result}")  # Debugging statement

                if result:
                    kad_link = result[0]
                    print(f"Fetched kadLink: {kad_link}")  # Debugging statement

                    if kad_link:
                        cleaned_kad_link = kad_link.strip()
                        redirect_url = f"https://www.aelb.gov.my/kadkuasa/{cleaned_kad_link}.html"
                        print(f"Redirect URL: {redirect_url}")  # Debugging statement

                        # Insert record into the `record` table
                        cursor.execute("""
                            INSERT INTO record (NoSiri, date, location)
                            VALUES (%s, %s, ST_PointFromText(%s))
                        """, [no_siri, datetime.now().date(), 'POINT(0 0)'])  # Replace 'POINT(0 0)' with actual location if available
                        print(f"Inserted record - NoSiri: {no_siri}, Date: {datetime.now().date()}, Location: POINT(0 0)")  # Debugging statement

                        return redirect(redirect_url)
                    else:
                        context['error_message'] = 'Invalid kadLink.'
                        print("Error: Invalid kadLink.")  # Debugging statement
                else:
                    context['error_message'] = 'Invalid SIRI or NoKP.'
                    print("Error: Invalid SIRI or NoKP.")  # Debugging statement

    except Exception as e:
        print('Error: ', e)  # Debugging statement for exceptions
        return render(request, 'h.html')

    return render(request, "7UserAuthorized.html", context)'''