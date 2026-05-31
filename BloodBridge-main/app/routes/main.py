from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import BloodRequest, Donation, BloodInventory, BloodDrive, Hospital, Donor, DriveRegistration, BloodBank, User
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    # Get recent blood drives
    upcoming_drives = BloodDrive.query.filter(
        BloodDrive.start_date > datetime.utcnow(),
        BloodDrive.status.in_(['UPCOMING', 'scheduled'])
    ).order_by(BloodDrive.start_date).limit(3).all()
    
    # Get urgent blood requests
    urgent_requests = BloodRequest.query.filter(
        BloodRequest.status == 'PENDING',
        BloodRequest.priority.in_(['CRITICAL', 'HIGH'])
    ).order_by(BloodRequest.created_at.desc()).limit(5).all()
    
    return render_template('main/index.html',
                         upcoming_drives=upcoming_drives,
                         urgent_requests=urgent_requests)

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.user_type == 'admin':
        return redirect(url_for('admin.dashboard'))

    elif current_user.user_type == 'donor':
        # Get donor's upcoming donations (now pending/accepted)
        pending_donations = Donation.query.filter(
            Donation.donor_id == current_user.id,
            Donation.status == 'PENDING'
        ).order_by(Donation.created_at.desc()).all()

        accepted_donations = Donation.query.filter(
            Donation.donor_id == current_user.id,
            Donation.status == 'ACCEPTED'
        ).order_by(Donation.donation_date.desc()).all()

        rejected_donations = Donation.query.filter(
            Donation.donor_id == current_user.id,
            Donation.status == 'REJECTED'
        ).order_by(Donation.created_at.desc()).all()

        # Get donor's recent completed donations
        recent_completed_donations = Donation.query.filter_by(
            donor_id=current_user.id,
            status='COMPLETED'
        ).order_by(Donation.donation_date.desc()).limit(5).all()

        # Get registered blood drives
        registered_drives = DriveRegistration.query.filter(
            DriveRegistration.donor_id == current_user.id,
            DriveRegistration.status.in_(['REGISTERED', 'ATTENDED'])
        ).join(BloodDrive).order_by(BloodDrive.start_date.desc()).all()

        return render_template('main/donor_dashboard.html',
                               pending_donations=pending_donations,
                               accepted_donations=accepted_donations,
                               rejected_donations=rejected_donations,
                               recent_completed_donations=recent_completed_donations,
                               registered_drives=registered_drives)

    elif current_user.user_type == 'hospital':
        # Get hospital's pending blood requests
        pending_requests = BloodRequest.query.filter_by(
            hospital_id=current_user.id,
            status='PENDING'
        ).order_by(BloodRequest.created_at.desc()).all()

        # Get hospital's accepted blood requests
        accepted_requests = BloodRequest.query.filter_by(
            hospital_id=current_user.id,
            status='ACCEPTED'
        ).order_by(BloodRequest.created_at.desc()).all()

        # Get hospital's rejected blood requests
        rejected_requests = BloodRequest.query.filter_by(
            hospital_id=current_user.id,
            status='REJECTED'
        ).order_by(BloodRequest.created_at.desc()).all()

        # Get recently fulfilled requests
        fulfilled_requests = BloodRequest.query.filter_by(
            hospital_id=current_user.id,
            status='FULFILLED'
        ).order_by(BloodRequest.created_at.desc()).limit(5).all()

        return render_template('main/hospital_dashboard.html',
                               pending_requests=pending_requests,
                               accepted_requests=accepted_requests,
                               rejected_requests=rejected_requests,
                               fulfilled_requests=fulfilled_requests)

    elif current_user.user_type == 'blood_bank':
        return redirect(url_for('blood_bank.dashboard'))
    else:
        return redirect(url_for('main.index'))

@bp.route('/blood-drives')
def blood_drives():
    page = request.args.get('page', 1, type=int)
    drives = BloodDrive.query.filter(
        BloodDrive.start_date > datetime.utcnow()
    ).order_by(BloodDrive.start_date).paginate(
        page=page, per_page=9, error_out=False)
    
    return render_template('main/blood_drives.html', drives=drives)

@bp.route('/blood-drive/<int:id>')
def blood_drive_detail(id):
    drive = BloodDrive.query.get_or_404(id)
    
    organizer_name = None
    if drive.organizer_id:
        organizer = User.query.get(drive.organizer_id)
        if organizer:
            if isinstance(organizer, BloodBank):
                organizer_name = organizer.bank_name
            else:
                organizer_name = f"{organizer.first_name} {organizer.last_name}"

    now = datetime.utcnow()
    status_text = ""
    days_remaining = None

    if drive.status == 'CANCELLED':
        status_text = 'CANCELLED'
    elif now < drive.start_date:
        status_text = "UPCOMING"
        time_until_start = drive.start_date - now
        days_remaining = time_until_start.days
    elif drive.start_date <= now <= drive.end_date:
        status_text = "RUNNING"
        time_until_end = drive.end_date - now
        days_remaining = time_until_end.days if time_until_end.total_seconds() > 0 else 0
    else:
        status_text = "COMPLETED"
    
    return render_template('main/blood_drive_detail.html', 
                           drive=drive, 
                           organizer_name=organizer_name,
                           status_text=status_text,
                           days_remaining=days_remaining)

@bp.route('/emergency-requests')
def emergency_requests():
    page = request.args.get('page', 1, type=int)
    requests = BloodRequest.query.filter(
        BloodRequest.status == 'PENDING',
        BloodRequest.priority.in_(['CRITICAL', 'HIGH'])
    ).order_by(BloodRequest.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False)
    
    return render_template('main/emergency_requests.html', requests=requests)

@bp.route('/about')
def about():
    return render_template('main/about.html')

@bp.route('/contact')
def contact():
    return render_template('main/contact.html')

@bp.route('/blood-inventory')
def blood_inventory():
    # Get all blood inventory records
    inventory_records = BloodInventory.query.all()
    
    # Create a dictionary of blood type to units available
    inventory = {}
    for record in inventory_records:
        inventory[record.blood_type] = inventory.get(record.blood_type, 0) + record.units_available
    
    return render_template('main/blood_inventory.html', inventory=inventory)

@bp.route('/create-emergency-request', methods=['POST'])
@login_required
def create_emergency_request():
    if current_user.user_type != 'hospital':
        flash('Only hospitals can create emergency requests.', 'error')
        return redirect(url_for('main.emergency_requests'))
    flash('Please submit emergency requests from the hospital request form.', 'info')
    return redirect(url_for('hospital.create_request'))

@bp.route('/donate', methods=['GET'])
@login_required
def donate():
    if current_user.user_type != 'donor':
        flash('Only donors can access this page.', 'error')
        return redirect(url_for('main.index'))
    accepted_requests = BloodRequest.query.filter_by(
        status='ACCEPTED',
        blood_type=current_user.blood_type
    ).order_by(BloodRequest.deadline).all()
    return render_template('main/donate.html', accepted_requests=accepted_requests)

@bp.route('/record-donation', methods=['POST'])
@login_required
def record_donation():
    if current_user.user_type != 'donor':
        flash('Only donors can record donations.', 'error')
        return redirect(url_for('main.index'))
    
    # Get form data
    blood_type = request.form.get('blood_type')
    units = request.form.get('units', type=int)
    request_id = request.form.get('request_id', type=int)
    try:
        donation_date = datetime.strptime(request.form.get('donation_date'), '%Y-%m-%dT%H:%M')
    except (TypeError, ValueError):
        flash('Please choose a valid donation date.', 'error')
        return redirect(url_for('main.donate'))
    notes = request.form.get('notes')

    if units is None or units < 1 or units > 2:
        flash('Donation units must be between 1 and 2.', 'error')
        return redirect(url_for('main.donate'))

    if blood_type != current_user.blood_type:
        flash('Donation blood type must match your registered blood type.', 'error')
        return redirect(url_for('main.donate'))

    last_donation = Donation.query.filter_by(
        donor_id=current_user.id, status='COMPLETED'
    ).order_by(Donation.donation_date.desc()).first()
    if last_donation and (donation_date - last_donation.donation_date).days < 56:
        flash('You must wait 56 days between completed donations.', 'error')
        return redirect(url_for('main.donate'))

    linked_request = None
    if request_id:
        linked_request = BloodRequest.query.get_or_404(request_id)
        if linked_request.status != 'ACCEPTED' or linked_request.blood_type != blood_type:
            flash('The selected blood request is not open for this blood type.', 'error')
            return redirect(url_for('main.donate'))
    
    # Create donation record with PENDING status
    donation = Donation(
        donor_id=current_user.id,
        request_id=linked_request.id if linked_request else None,
        blood_type=blood_type,
        units=units,
        donation_date=donation_date,
        notes=notes,
        status='PENDING'  # Set to PENDING for admin review
    )
    
    # Save changes
    db.session.add(donation)
    db.session.commit()
    
    flash('Donation request submitted successfully and is awaiting admin approval!', 'success')
    return redirect(url_for('donor.donation_history')) # Redirect to donor donation history to see pending status

@bp.route('/submit-emergency-request', methods=['POST'])
@login_required
def submit_emergency_request():
    if current_user.user_type != 'hospital':
        flash('Only hospitals can create emergency requests.', 'error')
        return redirect(url_for('main.emergency_requests'))
    flash('Please submit emergency requests from the hospital request form.', 'info')
    return redirect(url_for('hospital.create_request'))
