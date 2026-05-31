from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import BloodRequest, Donation, Hospital
from datetime import datetime

bp = Blueprint('hospital', __name__, url_prefix='/hospital')

@bp.route('/profile')
@login_required
def profile():
    if not isinstance(current_user, Hospital):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    # Get recent blood requests
    recent_requests = BloodRequest.query.filter_by(
        hospital_id=current_user.id
    ).order_by(BloodRequest.created_at.desc()).limit(5).all()
    
    # Get recent donations
    recent_donations = Donation.query.join(BloodRequest).filter(
        BloodRequest.hospital_id == current_user.id,
        Donation.status == 'COMPLETED'
    ).order_by(Donation.donation_date.desc()).limit(5).all()
    
    return render_template('hospital/profile.html',
                         recent_requests=recent_requests,
                         recent_donations=recent_donations)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if not isinstance(current_user, Hospital):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', '').strip()
        current_user.last_name = request.form.get('last_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.address = request.form.get('address', '').strip()
        current_user.hospital_name = request.form.get('hospital_name', '').strip()
        current_user.license_number = request.form.get('license_number', '').strip()
        current_user.emergency_contact = request.form.get('emergency_contact', '').strip()
        if not current_user.hospital_name:
            flash('Hospital name is required.', 'error')
            return render_template('hospital/edit_profile.html')
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('hospital.profile'))
    return render_template('hospital/edit_profile.html')

@bp.route('/blood-requests')
@login_required
def blood_requests():
    if not isinstance(current_user, Hospital):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    requests = BloodRequest.query.filter_by(
        hospital_id=current_user.id
    ).order_by(BloodRequest.created_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    
    return render_template('hospital/blood_requests.html', requests=requests)

@bp.route('/create-request', methods=['GET', 'POST'])
@login_required
def create_request():
    if not isinstance(current_user, Hospital):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        blood_type = request.form.get('blood_type')
        units_needed = request.form.get('units_needed', type=int)
        priority = request.form.get('priority')
        patient_details = request.form.get('patient_details')
        deadline_value = request.form.get('deadline')

        if not all([blood_type, units_needed, priority, patient_details, deadline_value]):
            flash('Please complete all request details.', 'error')
            return render_template('hospital/create_request.html')

        if units_needed < 1:
            flash('Units needed must be at least 1.', 'error')
            return render_template('hospital/create_request.html')

        try:
            deadline = datetime.strptime(deadline_value, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Please enter a valid deadline.', 'error')
            return render_template('hospital/create_request.html')
        
        blood_request = BloodRequest(
            hospital_id=current_user.id,
            requester_id=current_user.id,
            blood_type=blood_type,
            units_needed=units_needed,
            priority=priority,
            patient_details=patient_details,
            deadline=deadline,
            status='PENDING'
        )
        
        db.session.add(blood_request)
        db.session.commit()
        
        flash('Blood request created successfully and is awaiting admin approval!', 'success')
        return redirect(url_for('hospital.blood_requests'))
    
    return render_template('hospital/create_request.html')

@bp.route('/request/<int:id>')
@login_required
def request_detail(id):
    if not isinstance(current_user, Hospital):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    request = BloodRequest.query.get_or_404(id)
    
    if request.hospital_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    # Get donations for this request
    donations = Donation.query.filter_by(
        request_id=request.id
    ).order_by(Donation.donation_date).all()
    
    return render_template('hospital/request_detail.html',
                         request=request,
                         donations=donations)

@bp.route('/cancel-request/<int:id>', methods=['POST'])
@login_required
def cancel_request(id):
    if not isinstance(current_user, Hospital):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    request = BloodRequest.query.get_or_404(id)
    
    if request.hospital_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    if request.status != 'PENDING':
        flash('Cannot cancel a request that is not pending', 'error')
        return redirect(url_for('hospital.request_detail', id=id))
    
    request.status = 'CANCELLED'
    db.session.commit()
    
    flash('Request cancelled successfully', 'success')
    return redirect(url_for('hospital.blood_requests'))

@bp.route('/update-request/<int:id>', methods=['POST'])
@login_required
def update_request(id):
    if not isinstance(current_user, Hospital):
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    blood_request = BloodRequest.query.get_or_404(id)
    
    if blood_request.hospital_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    if blood_request.status != 'PENDING':
        flash('Cannot update a request that is not pending', 'error')
        return redirect(url_for('hospital.request_detail', id=id))
    
    units_needed = request.form.get('units_needed', type=int)
    deadline_value = request.form.get('deadline')
    if not units_needed or units_needed < 1 or not deadline_value:
        flash('Please enter valid request details.', 'error')
        return redirect(url_for('hospital.request_detail', id=id))

    try:
        deadline = datetime.strptime(deadline_value, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Please enter a valid deadline.', 'error')
        return redirect(url_for('hospital.request_detail', id=id))

    blood_request.units_needed = units_needed
    blood_request.priority = request.form.get('priority')
    blood_request.patient_details = request.form.get('patient_details')
    blood_request.deadline = deadline
    
    db.session.commit()
    
    flash('Request updated successfully', 'success')
    return redirect(url_for('hospital.request_detail', id=id)) 
