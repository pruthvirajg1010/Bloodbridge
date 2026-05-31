from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Donation, Donor, BloodDrive, DriveRegistration
from datetime import datetime

bp = Blueprint('donor', __name__, url_prefix='/donor')

@bp.route('/profile')
@login_required
def profile():
    if not isinstance(current_user, Donor):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    # Get donation history
    donations = Donation.query.filter_by(donor_id=current_user.id)\
        .order_by(Donation.donation_date.desc()).all()
    
    # Get registered blood drives
    registered_drives = DriveRegistration.query.filter(
        DriveRegistration.donor_id == current_user.id,
        DriveRegistration.status.in_(['REGISTERED', 'ATTENDED'])
    ).join(BloodDrive).order_by(BloodDrive.start_date).all()
    
    return render_template('donor/profile.html',
                         donations=donations,
                         registered_drives=registered_drives)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if not isinstance(current_user, Donor):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', '').strip()
        current_user.last_name = request.form.get('last_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.address = request.form.get('address', '').strip()
        current_user.emergency_contact = request.form.get('emergency_contact', '').strip()
        current_user.medical_conditions = request.form.get('medical_conditions', '').strip()
        blood_type = request.form.get('blood_type')
        if blood_type not in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
            flash('Select a valid blood type.', 'error')
            return render_template('donor/edit_profile.html')
        current_user.blood_type = blood_type
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('donor.profile'))
    return render_template('donor/edit_profile.html')

@bp.route('/donation-history')
@login_required
def donation_history():
    if not isinstance(current_user, Donor):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    donations = Donation.query.filter_by(donor_id=current_user.id)\
        .order_by(Donation.donation_date.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    
    return render_template('donor/donation_history.html', donations=donations)

@bp.route('/schedule-donation', methods=['GET', 'POST'])
@login_required
def schedule_donation():
    if not isinstance(current_user, Donor):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        donation_date = datetime.strptime(
            request.form.get('donation_date'), '%Y-%m-%d')
        
        # Check if donor is eligible
        last_donation = Donation.query.filter_by(
            donor_id=current_user.id,
            status='COMPLETED'
        ).order_by(Donation.donation_date.desc()).first()
        
        if last_donation and (donation_date - last_donation.donation_date).days < 56:
            flash('You must wait 56 days between donations', 'error')
            return redirect(url_for('donor.schedule_donation'))
        
        donation = Donation(
            donor_id=current_user.id,
            blood_type=current_user.blood_type,
            donation_date=donation_date,
            status='PENDING'
        )
        
        db.session.add(donation)
        db.session.commit()
        
        flash('Donation scheduled successfully and is awaiting admin approval!', 'success')
        return redirect(url_for('donor.donation_history'))
    
    return redirect(url_for('main.donate'))

@bp.route('/register-drive/<int:drive_id>', methods=['POST'])
@login_required
def register_for_drive(drive_id):
    if not isinstance(current_user, Donor):
        flash('Only donors can register for blood drives.', 'error')
        return redirect(url_for('main.index'))
    
    drive = BloodDrive.query.get_or_404(drive_id)
    if drive.status == 'CANCELLED' or drive.end_date < datetime.utcnow():
        flash('Registration is closed for this blood drive.', 'error')
        return redirect(url_for('main.blood_drive_detail', id=drive_id))
    
    # Check if already registered
    existing_registration = DriveRegistration.query.filter_by(
        donor_id=current_user.id,
        drive_id=drive_id
    ).first()
    
    if existing_registration:
        if existing_registration.status == 'CANCELLED':
            existing_registration.status = 'REGISTERED'
            existing_registration.registration_date = datetime.utcnow()
            db.session.commit()
            flash('Successfully registered for the blood drive again!', 'success')
        else:
            flash('You are already registered for this blood drive.', 'info')
        return redirect(url_for('main.blood_drive_detail', id=drive_id))
    
    # Create new registration
    registration = DriveRegistration(
        donor_id=current_user.id,
        drive_id=drive_id,
        status='REGISTERED'
    )
    
    try:
        db.session.add(registration)
        db.session.commit()
        flash('Successfully registered for the blood drive!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering for blood drive: {str(e)}', 'error')
    
    return redirect(url_for('main.blood_drive_detail', id=drive_id))

@bp.route('/cancel-registration/<int:registration_id>', methods=['POST'])
@login_required
def cancel_registration(registration_id):
    if not isinstance(current_user, Donor):
        flash('Only donors can cancel registrations.', 'error')
        return redirect(url_for('main.index'))
    
    registration = DriveRegistration.query.get_or_404(registration_id)
    
    # Verify ownership
    if registration.donor_id != current_user.id:
        flash('You can only cancel your own registrations.', 'error')
        return redirect(url_for('main.index'))
    
    try:
        if registration.status != 'REGISTERED':
            flash('Only an active registration can be cancelled.', 'error')
            return redirect(url_for('main.blood_drive_detail', id=registration.drive_id))
        registration.status = 'CANCELLED'
        db.session.commit()
        flash('Registration cancelled successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling registration: {str(e)}', 'error')
    
    return redirect(url_for('main.blood_drive_detail', id=registration.drive_id))
