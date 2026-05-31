from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import BloodBank, BloodDrive, BloodInventory, Donation, DriveRegistration


bp = Blueprint('blood_bank', __name__, url_prefix='/blood-bank')


def bank_required():
    if not isinstance(current_user, BloodBank):
        flash('Access denied. Only blood bank users can access this page.', 'error')
        return False
    return True


def parse_drive_form():
    title = request.form.get('title', '').strip()
    location = request.form.get('location', '').strip()
    description = request.form.get('description', '').strip()
    start_value = request.form.get('start_date', '')
    end_value = request.form.get('end_date', '')
    if not all([title, location, start_value, end_value]):
        raise ValueError('Please complete all blood drive details.')
    try:
        start_date = datetime.strptime(start_value, '%Y-%m-%dT%H:%M')
        end_date = datetime.strptime(end_value, '%Y-%m-%dT%H:%M')
    except ValueError as exc:
        raise ValueError('Please enter valid drive dates.') from exc
    if end_date <= start_date:
        raise ValueError('The end time must be after the start time.')
    return title, location, description, start_date, end_date


@bp.route('/dashboard')
@login_required
def dashboard():
    if not bank_required():
        return redirect(url_for('main.index'))

    drives = BloodDrive.query.filter_by(organizer_id=current_user.id)
    inventory = BloodInventory.query.filter_by(blood_bank_id=current_user.id).all()
    recent_drives = drives.order_by(BloodDrive.start_date.desc()).limit(5).all()
    total_registrations = DriveRegistration.query.join(BloodDrive).filter(
        BloodDrive.organizer_id == current_user.id
    ).count()

    return render_template(
        'blood_bank/dashboard.html',
        total_drives=drives.count(),
        upcoming_drives=drives.filter(
            BloodDrive.end_date >= datetime.utcnow(),
            BloodDrive.status != 'CANCELLED'
        ).count(),
        total_registrations=total_registrations,
        inventory=inventory,
        low_stock=[item for item in inventory if item.units_available < 10],
        recent_drives=recent_drives
    )


@bp.route('/profile')
@login_required
def profile():
    if not bank_required():
        return redirect(url_for('main.index'))

    inventory = BloodInventory.query.filter_by(blood_bank_id=current_user.id).all()
    recent_donations = Donation.query.filter(
        Donation.status.in_(['ACCEPTED', 'COMPLETED']),
        Donation.donation_date > datetime.utcnow() - timedelta(days=7)
    ).order_by(Donation.donation_date.desc()).limit(5).all()
    return render_template(
        'blood_bank/profile.html',
        inventory=inventory,
        low_stock=[item for item in inventory if item.units_available < 10],
        recent_donations=recent_donations
    )

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if not bank_required():
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', '').strip()
        current_user.last_name = request.form.get('last_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.address = request.form.get('address', '').strip()
        current_user.bank_name = request.form.get('bank_name', '').strip()
        current_user.license_number = request.form.get('license_number', '').strip()
        current_user.emergency_contact = request.form.get('emergency_contact', '').strip()
        if not current_user.bank_name:
            flash('Blood bank name is required.', 'error')
            return render_template('blood_bank/edit_profile.html')
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('blood_bank.profile'))
    return render_template('blood_bank/edit_profile.html')


@bp.route('/inventory')
@login_required
def inventory():
    if not bank_required():
        return redirect(url_for('main.index'))
    items = BloodInventory.query.filter_by(blood_bank_id=current_user.id).all()
    return render_template('blood_bank/inventory.html', inventory=items)


@bp.route('/update-inventory', methods=['POST'])
@login_required
def update_inventory():
    if not bank_required():
        return redirect(url_for('main.index'))

    blood_type = request.form.get('blood_type')
    units = request.form.get('units', type=int)
    valid_types = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    if blood_type not in valid_types or units is None or units < 0:
        flash('Please provide a valid blood type and non-negative unit count.', 'error')
        return redirect(url_for('blood_bank.inventory'))

    item = BloodInventory.query.filter_by(
        blood_bank_id=current_user.id,
        blood_type=blood_type
    ).first()
    if item:
        item.units_available = units
    else:
        db.session.add(BloodInventory(
            blood_bank_id=current_user.id,
            blood_type=blood_type,
            units_available=units
        ))
    db.session.commit()
    flash('Inventory updated successfully.', 'success')
    return redirect(url_for('blood_bank.inventory'))


@bp.route('/blood-drives')
@login_required
def blood_drives():
    if not bank_required():
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type=int)
    drives = BloodDrive.query.filter_by(organizer_id=current_user.id).order_by(
        BloodDrive.start_date.desc()
    ).paginate(page=page, per_page=10, error_out=False)
    return render_template('blood_bank/blood_drives.html', drives=drives)


@bp.route('/create-drive', methods=['GET', 'POST'])
@bp.route('/schedule-drive', methods=['GET', 'POST'])
@login_required
def create_drive():
    if not bank_required():
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        try:
            title, location, description, start_date, end_date = parse_drive_form()
        except ValueError as error:
            flash(str(error), 'error')
            return render_template('blood_bank/create_drive.html')
        drive = BloodDrive(
            organizer_id=current_user.id,
            title=title,
            description=description,
            location=location,
            start_date=start_date,
            end_date=end_date,
            status='UPCOMING'
        )
        db.session.add(drive)
        db.session.commit()
        flash('Blood drive created successfully.', 'success')
        return redirect(url_for('blood_bank.blood_drives'))
    return render_template('blood_bank/create_drive.html')


@bp.route('/drive/<int:id>')
@login_required
def drive_detail(id):
    if not bank_required():
        return redirect(url_for('main.index'))
    drive = BloodDrive.query.get_or_404(id)
    if drive.organizer_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('blood_bank.blood_drives'))
    return render_template('blood_bank/drive_detail.html', drive=drive, registrations=drive.registrations)


@bp.route('/registration/<int:registration_id>/attend', methods=['POST'])
@login_required
def mark_attendance(registration_id):
    if not bank_required():
        return redirect(url_for('main.index'))
    registration = DriveRegistration.query.get_or_404(registration_id)
    if registration.drive.organizer_id != current_user.id:
        flash('You are not authorized to update this registration.', 'error')
        return redirect(url_for('blood_bank.dashboard'))
    if registration.status != 'REGISTERED':
        flash('Only active registrations can be marked attended.', 'error')
        return redirect(url_for('blood_bank.drive_detail', id=registration.drive_id))
    registration.status = 'ATTENDED'
    db.session.commit()
    flash('Donor attendance recorded.', 'success')
    return redirect(url_for('blood_bank.drive_detail', id=registration.drive_id))


@bp.route('/edit-drive/<int:drive_id>', methods=['GET', 'POST'])
@bp.route('/update-drive/<int:drive_id>', methods=['POST'])
@login_required
def edit_drive(drive_id):
    if not bank_required():
        return redirect(url_for('main.index'))
    drive = BloodDrive.query.get_or_404(drive_id)
    if drive.organizer_id != current_user.id:
        flash('You are not authorized to edit this blood drive.', 'error')
        return redirect(url_for('blood_bank.dashboard'))
    if request.method == 'POST':
        try:
            title, location, description, start_date, end_date = parse_drive_form()
        except ValueError as error:
            flash(str(error), 'error')
            return render_template('blood_bank/create_drive.html', drive=drive, is_edit=True)
        drive.title = title
        drive.location = location
        drive.description = description
        drive.start_date = start_date
        drive.end_date = end_date
        drive.status = request.form.get('status', drive.status)
        db.session.commit()
        flash('Blood drive updated successfully.', 'success')
        return redirect(url_for('blood_bank.drive_detail', id=drive.id))
    return render_template('blood_bank/create_drive.html', drive=drive, is_edit=True)


@bp.route('/delete-drive/<int:drive_id>', methods=['POST'])
@login_required
def delete_drive(drive_id):
    if not bank_required():
        return redirect(url_for('main.index'))
    drive = BloodDrive.query.get_or_404(drive_id)
    if drive.organizer_id != current_user.id:
        flash('You are not authorized to delete this blood drive.', 'error')
        return redirect(url_for('blood_bank.dashboard'))
    db.session.delete(drive)
    db.session.commit()
    flash('Blood drive deleted successfully.', 'success')
    return redirect(url_for('blood_bank.blood_drives'))
