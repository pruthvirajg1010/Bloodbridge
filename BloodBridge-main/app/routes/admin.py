from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import BloodRequest, Donation, BloodInventory, BloodAllocation, Donor, BloodDrive, BloodBank, User
from app.forms import ApproveRejectForm, BloodDriveForm
from functools import wraps

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.user_type != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # Get pending blood requests
    pending_requests = BloodRequest.query.filter_by(status='PENDING').order_by(BloodRequest.created_at.desc()).all()
    
    # Get pending donations
    pending_donations = Donation.query.filter_by(status='PENDING').order_by(Donation.created_at.desc()).all()
    accepted_requests = BloodRequest.query.filter_by(status='ACCEPTED').order_by(BloodRequest.created_at.desc()).all()
    accepted_donations = Donation.query.filter_by(status='ACCEPTED').order_by(Donation.created_at.desc()).all()
    
    # Get all blood requests for the table
    blood_requests = BloodRequest.query.order_by(BloodRequest.created_at.desc()).all()
    
    # Get all donations for the table
    donations = Donation.query.order_by(Donation.created_at.desc()).all()
    
    # Get total donors
    total_donors = Donor.query.count()

    blood_drives = BloodDrive.query.order_by(BloodDrive.start_date.desc()).all()
    blood_banks = BloodBank.query.filter_by(is_active=True).order_by(BloodBank.bank_name).all()
    form = ApproveRejectForm()
    return render_template('admin/dashboard.html', 
                           pending_requests=pending_requests, 
                           pending_donations=pending_donations, 
                           accepted_requests=accepted_requests,
                           accepted_donations=accepted_donations,
                           blood_requests=blood_requests,
                           donations=donations,
                           total_donors=total_donors, 
                           blood_drives=blood_drives,
                           blood_banks=blood_banks,
                           form=form)

@bp.route('/blood-request/<int:request_id>/<action>', methods=['POST'])
@login_required
@admin_required
def manage_blood_request(request_id, action):
    blood_request = BloodRequest.query.get_or_404(request_id)
    form = ApproveRejectForm()
    if form.validate_on_submit():
        blood_request.admin_notes = form.admin_notes.data
        if action == 'accept' and blood_request.status == 'PENDING':
            blood_request.status = 'ACCEPTED'
            flash('Blood request accepted and ready for fulfilment.', 'success')
        elif action == 'reject' and blood_request.status == 'PENDING':
            blood_request.status = 'REJECTED'
            flash('Blood request rejected.', 'success')
        elif action == 'fulfill' and blood_request.status == 'ACCEPTED':
            inventory_items = BloodInventory.query.filter_by(
                blood_type=blood_request.blood_type
            ).order_by(BloodInventory.units_available.desc()).all()
            available_units = sum(item.units_available for item in inventory_items)
            if available_units < blood_request.units_needed:
                flash('Not enough inventory is available to fulfil this request.', 'error')
                return redirect(url_for('admin.dashboard'))
            units_remaining = blood_request.units_needed
            for item in inventory_items:
                deducted_units = min(item.units_available, units_remaining)
                if deducted_units == 0:
                    continue
                item.units_available -= deducted_units
                db.session.add(BloodAllocation(
                    request_id=blood_request.id,
                    inventory_id=item.id,
                    units_allocated=deducted_units
                ))
                units_remaining -= deducted_units
                if units_remaining == 0:
                    break
            blood_request.status = 'FULFILLED'
            flash('Blood request fulfilled and inventory updated.', 'success')
        else:
            flash('This request action is no longer available.', 'error')
        db.session.commit()
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'error')
    return redirect(url_for('admin.dashboard'))

@bp.route('/donation/<int:donation_id>/<action>', methods=['POST'])
@login_required
@admin_required
def manage_donation(donation_id, action):
    donation = Donation.query.get_or_404(donation_id)
    form = ApproveRejectForm()
    if form.validate_on_submit():
        donation.admin_notes = form.admin_notes.data
        if action == 'accept' and donation.status == 'PENDING':
            donation.status = 'ACCEPTED'
            flash('Donation accepted and awaiting completion.', 'success')
        elif action == 'complete' and donation.status == 'ACCEPTED':
            blood_bank_id = request.form.get('blood_bank_id', type=int)
            receiving_bank = BloodBank.query.filter_by(id=blood_bank_id, is_active=True).first()
            if not receiving_bank:
                flash('Select an active blood bank to receive this donation.', 'error')
                return redirect(url_for('admin.dashboard'))
            donation.status = 'COMPLETED'
            blood_inventory = BloodInventory.query.filter_by(
                blood_bank_id=receiving_bank.id,
                blood_type=donation.blood_type
            ).first()
            if blood_inventory:
                blood_inventory.units_available += donation.units
            else:
                db.session.add(BloodInventory(
                    blood_bank_id=receiving_bank.id,
                    blood_type=donation.blood_type,
                    units_available=donation.units
                ))
            donation.donor.last_donation = donation.donation_date or donation.updated_at
            flash('Donation completed and added to inventory.', 'success')
        elif action == 'reject' and donation.status == 'PENDING':
            donation.status = 'REJECTED'
            flash('Donation rejected.', 'success')
        else:
            flash('This donation action is no longer available.', 'error')
        db.session.commit()
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'error')
    return redirect(url_for('admin.dashboard'))

@bp.route('/schedule_drive', methods=['GET', 'POST'])
@login_required
@admin_required
def schedule_drive():
    form = BloodDriveForm()
    if form.validate_on_submit():
        new_drive = BloodDrive(
            title=form.title.data,
            description=form.description.data,
            location=form.location.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            organizer_id=current_user.id # Assuming admin is the organizer
        )
        db.session.add(new_drive)
        db.session.commit()
        flash('Blood drive scheduled successfully!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/schedule_drive.html', form=form)

@bp.route('/edit_drive/<int:drive_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_drive(drive_id):
    drive = BloodDrive.query.get_or_404(drive_id)
    form = BloodDriveForm(obj=drive)
    if form.validate_on_submit():
        drive.title = form.title.data
        drive.description = form.description.data
        drive.location = form.location.data
        drive.start_date = form.start_date.data
        drive.end_date = form.end_date.data
        db.session.commit()
        flash('Blood drive updated successfully!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/schedule_drive.html', form=form, drive=drive) # Reusing schedule_drive template

@bp.route('/delete_drive/<int:drive_id>', methods=['POST'])
@login_required
@admin_required
def delete_drive(drive_id):
    drive = BloodDrive.query.get_or_404(drive_id)
    db.session.delete(drive)
    db.session.commit()
    flash('Blood drive deleted successfully!', 'success')
    return redirect(url_for('admin.dashboard')) 
