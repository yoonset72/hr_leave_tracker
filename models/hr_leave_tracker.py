from odoo import models, fields, api
from datetime import date
import logging

_logger = logging.getLogger(__name__)

class HrLeaveTracker(models.Model):
    _name = 'hr.leave.tracker'
    _description = 'HR Leave Tracker'
    _rec_name = 'name'
    _order = 'employee_id, year, leave_type_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    leave_type_id = fields.Many2one('hr.leave.type', string='Leave Type', required=True, ondelete='cascade')
    year = fields.Char(string='Year', required=True, default=lambda self: str(date.today().year))
    
    total_allocation = fields.Float(string='Total Allocation', default=0.0)
    taken_leaves = fields.Float(string='Taken Leaves', default=0.0)
    pending_requests = fields.Float(string='Pending Requests', default=0.0)
    current_balance = fields.Float(string='Current Balance', compute='_compute_current_balance', store=True)
    annual_carry = fields.Float(string="Carry Forward", default=0.0)
    expired_carry = fields.Float(string="Expired Carrry", default=0.0)
    
    employee_name = fields.Char(string='Employee Name', compute='_compute_display_fields', store=True)
    employee_number = fields.Char(string='Employee Number', compute='_compute_display_fields', store=True)
    leave_type_name = fields.Char(string='Leave Type Name', compute='_compute_display_fields', store=True)
    department_id = fields.Many2one('hr.department', string='Department', compute='_compute_display_fields', store=True)
    name = fields.Char(string='Name', compute='_compute_name', store=True)

    carry_display = fields.Html(
        string="Carry / Expired",
        compute="_compute_carry_display",
        sanitize=False,   # allow raw HTML
        store=False
    )

    @api.depends('total_allocation', 'taken_leaves', 'annual_carry')
    def _compute_current_balance(self):
        for record in self:
            if record.leave_type_name and 'annual' in record.leave_type_name.lower():
                record.current_balance = record.total_allocation  - record.taken_leaves
            else:
                record.current_balance = record.total_allocation - record.taken_leaves


    @api.depends('employee_id', 'leave_type_id')
    def _compute_display_fields(self):
        for record in self:
            if record.employee_id:
                record.employee_name = record.employee_id.name or ''
                record.employee_number = getattr(record.employee_id, 'employee_number', str(record.employee_id.id))
                record.department_id = record.employee_id.department_id.id if record.employee_id.department_id else False
            else:
                record.employee_name = ''
                record.employee_number = ''
                record.department_id = False
            record.leave_type_name = record.leave_type_id.name if record.leave_type_id else ''

    @api.depends('employee_id', 'leave_type_id', 'year')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.leave_type_id and record.year:
                record.name = f"{record.employee_id.name} - {record.leave_type_id.name} ({record.year})"
            elif record.employee_id and record.year:
                record.name = f"{record.employee_id.name} ({record.year})"
            elif record.employee_id:
                record.name = record.employee_id.name
            else:
                record.name = "New Tracker"

    @api.onchange('employee_id', 'leave_type_id', 'year')
    def _onchange_employee_leave_type(self):
        """Update leave counts when employee, leave type, or year changes."""
        for record in self:
            record.total_allocation = 0.0
            record.taken_leaves = 0.0
            record.pending_requests = 0.0

            if record.employee_id and record.leave_type_id:
                # Total allocation: sum allocations for this employee and leave type
                allocations = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('holiday_status_id', '=', record.leave_type_id.id),
                    ('state', '=', 'validate'),
                ])
                record.total_allocation = sum(allocations.mapped('number_of_days'))

                # Taken leaves (validated) in the selected year
                leaves_taken = self.env['hr.leave'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('holiday_status_id', '=', record.leave_type_id.id),
                    ('state', '=', 'validate'),
                    ('request_date_from', '>=', f'{record.year}-01-01'),
                    ('request_date_to', '<=', f'{record.year}-12-31'),
                ])
                record.taken_leaves = sum(leaves_taken.mapped('number_of_days'))

                # Pending leaves (confirmed) in the selected year
                leaves_pending = self.env['hr.leave'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('holiday_status_id', '=', record.leave_type_id.id),
                    ('state', '=', 'confirm'),
                    ('request_date_from', '>=', f'{record.year}-01-01'),
                    ('request_date_to', '<=', f'{record.year}-12-31'),
                ])
                record.pending_requests = sum(leaves_pending.mapped('number_of_days'))

    def action_edit_details(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Edit {self.leave_type_name} - {self.employee_name}',
            'res_model': 'hr.leave.tracker',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class HrEmployeeLeaveOverview(models.Model):
    _name = 'hr.employee.leave.overview'
    _description = 'Employee Leave Balance Overview'
    _auto = False
    _rec_name = 'employee_name'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    employee_number = fields.Char(string='Employee ID')
    employee_name = fields.Char(string='Employee Name')
    department_id = fields.Many2one('hr.department', string='Department')
    department_name = fields.Char(string='Department Name')

    # Casual leave
    casual_total = fields.Float(string='Casual Total')
    casual_taken = fields.Float(string='Casual Taken')
    casual_pending = fields.Float(string='Casual Pending')
    casual_balance = fields.Float(string='Casual Balance')

    # Annual leave
    annual_total = fields.Float(string='Annual Total')
    annual_taken = fields.Float(string='Annual Taken')
    annual_pending = fields.Float(string='Annual Pending')
    annual_balance = fields.Float(string='Annual Balance')
    annual_carry = fields.Float(string="Carry Forward")
    expired_carry = fields.Float(string="Expired Carry")

    # Medical leave
    medical_total = fields.Float(string='Medical Total')
    medical_taken = fields.Float(string='Medical Taken')
    medical_pending = fields.Float(string='Medical Pending')
    medical_balance = fields.Float(string='Medical Balance')

    # Unpaid leave
    unpaid_total = fields.Float(string='Unpaid Total')
    unpaid_taken = fields.Float(string='Unpaid Taken')
    unpaid_pending = fields.Float(string='Unpaid Pending')
    unpaid_balance = fields.Float(string='Unpaid Balance')

    # Funeral leave
    funeral_total = fields.Float(string='Funeral Total')
    funeral_taken = fields.Float(string='Funeral Taken')
    funeral_pending = fields.Float(string='Funeral Pending')
    funeral_balance = fields.Float(string='Funeral Balance')

    # Marriage leave
    marriage_total = fields.Float(string='Marriage Total')
    marriage_taken = fields.Float(string='Marriage Taken')
    marriage_pending = fields.Float(string='Marriage Pending')
    marriage_balance = fields.Float(string='Marriage Balance')

    # Maternity leave
    maternity_total = fields.Float(string='Maternity Total')
    maternity_taken = fields.Float(string='Maternity Taken')
    maternity_pending = fields.Float(string='Maternity Pending')
    maternity_balance = fields.Float(string='Maternity Balance')

    # Paternity leave
    paternity_total = fields.Float(string='Paternity Total')
    paternity_taken = fields.Float(string='Paternity Taken')
    paternity_pending = fields.Float(string='Paternity Pending')
    paternity_balance = fields.Float(string='Paternity Balance')

    def init(self):
        """Create SQL view including total, taken, pending, balance, carry"""
        current_year = str(date.today().year)
        self.env.cr.execute("DROP VIEW IF EXISTS hr_employee_leave_overview CASCADE")
        
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW hr_employee_leave_overview AS (
                SELECT 
                    ROW_NUMBER() OVER (ORDER BY e.id) AS id,
                    e.id AS employee_id,
                    COALESCE(e.employee_number, CAST(e.id AS VARCHAR)) AS employee_number,
                    e.name AS employee_name,
                    e.department_id AS department_id,
                    d.name AS department_name,

                    -- Casual leave
                    COALESCE(casual.total_allocation,0) AS casual_total,
                    COALESCE(casual.taken_leaves,0) AS casual_taken,
                    COALESCE(casual.pending_requests,0) AS casual_pending,
                    COALESCE(casual.current_balance,0) AS casual_balance,

                    -- Annual leave
                    COALESCE(annual.total_allocation,0) AS annual_total,
                    COALESCE(annual.taken_leaves,0) AS annual_taken,
                    COALESCE(annual.pending_requests,0) AS annual_pending,
                    COALESCE(annual.current_balance,0) AS annual_balance,
                    COALESCE(annual.annual_carry,0) AS annual_carry,
                    COALESCE(annual.expired_carry,0) AS expired_carry,

                    -- Medical leave
                    COALESCE(medical.total_allocation,0) AS medical_total,
                    COALESCE(medical.taken_leaves,0) AS medical_taken,
                    COALESCE(medical.pending_requests,0) AS medical_pending,
                    COALESCE(medical.current_balance,0) AS medical_balance,

                    -- Unpaid leave
                    COALESCE(unpaid.total_allocation,0) AS unpaid_total,
                    COALESCE(unpaid.taken_leaves,0) AS unpaid_taken,
                    COALESCE(unpaid.pending_requests,0) AS unpaid_pending,
                    COALESCE(unpaid.current_balance,0) AS unpaid_balance,

                    -- Funeral leave
                    COALESCE(funeral.total_allocation,0) AS funeral_total,
                    COALESCE(funeral.taken_leaves,0) AS funeral_taken,
                    COALESCE(funeral.pending_requests,0) AS funeral_pending,
                    COALESCE(funeral.current_balance,0) AS funeral_balance,

                    -- Marriage leave
                    COALESCE(marriage.total_allocation,0) AS marriage_total,
                    COALESCE(marriage.taken_leaves,0) AS marriage_taken,
                    COALESCE(marriage.pending_requests,0) AS marriage_pending,
                    COALESCE(marriage.current_balance,0) AS marriage_balance,

                    -- Maternity leave
                    COALESCE(maternity.total_allocation,0) AS maternity_total,
                    COALESCE(maternity.taken_leaves,0) AS maternity_taken,
                    COALESCE(maternity.pending_requests,0) AS maternity_pending,
                    COALESCE(maternity.current_balance,0) AS maternity_balance,

                    -- Paternity leave
                    COALESCE(paternity.total_allocation,0) AS paternity_total,
                    COALESCE(paternity.taken_leaves,0) AS paternity_taken,
                    COALESCE(paternity.pending_requests,0) AS paternity_pending,
                    COALESCE(paternity.current_balance,0) AS paternity_balance

                FROM hr_employee e
                LEFT JOIN hr_department d ON e.department_id = d.id
                LEFT JOIN hr_leave_tracker casual ON e.id = casual.employee_id 
                    AND casual.leave_type_name ILIKE '%casual%' 
                    AND casual.year = '{current_year}'
                LEFT JOIN hr_leave_tracker annual ON e.id = annual.employee_id 
                    AND annual.leave_type_name ILIKE '%annual%' 
                    AND annual.year = '{current_year}'
                LEFT JOIN hr_leave_tracker medical ON e.id = medical.employee_id 
                    AND (medical.leave_type_name ILIKE '%medical%' OR medical.leave_type_name ILIKE '%sick%')
                    AND medical.year = '{current_year}'
                LEFT JOIN hr_leave_tracker unpaid ON e.id = unpaid.employee_id 
                    AND unpaid.leave_type_name ILIKE '%unpaid%' 
                    AND unpaid.year = '{current_year}'
                LEFT JOIN hr_leave_tracker funeral ON e.id = funeral.employee_id 
                    AND (funeral.leave_type_name ILIKE '%funeral%' OR funeral.leave_type_name ILIKE '%bereavement%')
                    AND funeral.year = '{current_year}'
                LEFT JOIN hr_leave_tracker marriage ON e.id = marriage.employee_id 
                    AND (marriage.leave_type_name ILIKE '%marriage%' OR marriage.leave_type_name ILIKE '%wedding%')
                    AND marriage.year = '{current_year}'
                LEFT JOIN hr_leave_tracker maternity ON e.id = maternity.employee_id 
                    AND maternity.leave_type_name ILIKE '%maternity%' 
                    AND maternity.year = '{current_year}'
                LEFT JOIN hr_leave_tracker paternity ON e.id = paternity.employee_id 
                    AND paternity.leave_type_name ILIKE '%paternity%' 
                    AND paternity.year = '{current_year}'
                WHERE e.active = TRUE
                ORDER BY e.name
            )
        """)



    def action_view_casual_details(self):
        return self._open_leave_details('casual')
    
    def action_view_annual_details(self):
        return self._open_leave_details('annual')
    
    def action_view_medical_details(self):
        return self._open_leave_details('medical')
    
    def action_view_unpaid_details(self):
        return self._open_leave_details('unpaid')
    
    def action_view_funeral_details(self):
        return self._open_leave_details('funeral')
    
    def action_view_marriage_details(self):
        return self._open_leave_details('marriage')





    def write(self, vals):
        """Redirect writes from the SQL view to hr.leave.tracker records"""
        year = str(date.today().year)

        # mapping of overview field → (leave type search keyword, tracker field)
        field_map = {
            'casual_total': ('casual', 'total_allocation'),
            'casual_taken': ('casual', 'taken_leaves'),
            'casual_pending': ('casual', 'pending_requests'),

            'annual_total': ('annual', 'total_allocation'),
            'annual_taken': ('annual', 'taken_leaves'),
            'annual_pending': ('annual', 'pending_requests'),

            'medical_total': ('medical', 'total_allocation'),
            'medical_taken': ('medical', 'taken_leaves'),
            'medical_pending': ('medical', 'pending_requests'),

            'unpaid_total': ('unpaid', 'total_allocation'),
            'unpaid_taken': ('unpaid', 'taken_leaves'),
            'unpaid_pending': ('unpaid', 'pending_requests'),

            'funeral_total': ('funeral', 'total_allocation'),
            'funeral_taken': ('funeral', 'taken_leaves'),
            'funeral_pending': ('funeral', 'pending_requests'),

            'marriage_total': ('marriage', 'total_allocation'),
            'marriage_taken': ('marriage', 'taken_leaves'),
            'marriage_pending': ('marriage', 'pending_requests'),

            'maternity_total': ('maternity', 'total_allocation'),
            'maternity_taken': ('maternity', 'taken_leaves'),
            'maternity_pending': ('maternity', 'pending_requests'),

            'paternity_total': ('paternity', 'total_allocation'),
            'paternity_taken': ('paternity', 'taken_leaves'),
            'paternity_pending': ('paternity', 'pending_requests'),
        }

        for rec in self:
            updates_by_type = {}

            # group updates per leave type
            for field, value in vals.items():
                if field in field_map:
                    leave_type_key, tracker_field = field_map[field]
                    updates_by_type.setdefault(leave_type_key, {})[tracker_field] = value

            # now apply grouped updates
            for leave_type_key, updates in updates_by_type.items():
                tracker = self.env['hr.leave.tracker'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('leave_type_name', 'ilike', f'%{leave_type_key}%'),
                    ('year', '=', year)
                ], limit=1)

                if tracker:
                    _logger.info("Updating %s tracker for %s: %s", leave_type_key, rec.employee_name, updates)
                    tracker.write(updates)
                else:
                    leave_type = self.env['hr.leave.type'].search([
                        ('name', 'ilike', f'%{leave_type_key}%')
                    ], limit=1)

                    if not leave_type:
                        _logger.warning("No leave type found for keyword '%s' when writing to %s", leave_type_key, rec.employee_name)
                        continue  # skip this type if leave_type is missing

                    values = {
                        'employee_id': rec.employee_id.id,
                        'leave_type_id': leave_type.id,
                        'year': year,
                    }
                    values.update(updates)

                    _logger.info("Creating %s tracker for %s: %s", leave_type_key, rec.employee_name, values)
                    self.env['hr.leave.tracker'].create(values)

        return True

    def action_view_maternity_details(self):
        return self._open_leave_details('maternity')
    
    def action_view_paternity_details(self):
        return self._open_leave_details('paternity')

    def _open_leave_details(self, leave_type):
        """Open detailed view for specific leave type"""
        # Find the tracker record for this employee and leave type
        current_year = str(date.today().year)
        
        tracker = self.env['hr.leave.tracker'].search([
            ('employee_id', '=', self.employee_id.id),
            ('leave_type_name', 'ilike', f'%{leave_type}%'),
            ('year', '=', current_year)
        ], limit=1)
        
        if tracker:
            return {
                'type': 'ir.actions.act_window',
                'name': f'{leave_type.title()} Leave Details - {self.employee_name}',
                'res_model': 'hr.leave.tracker',
                'res_id': tracker.id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Data',
                    'message': f'No {leave_type} leave data found for {self.employee_name}',
                    'type': 'warning',
                }
            }
    
    def write(self, vals):
        """Redirect writes from the SQL view to hr.leave.tracker records"""
        year = str(date.today().year)

        # mapping of overview field → (leave type search keyword, tracker field)
        field_map = {
            'casual_total': ('casual', 'total_allocation'),
            'casual_taken': ('casual', 'taken_leaves'),
            'casual_pending': ('casual', 'pending_requests'),

            'annual_total': ('annual', 'total_allocation'),
            'annual_taken': ('annual', 'taken_leaves'),
            'annual_pending': ('annual', 'pending_requests'),

            'medical_total': ('medical', 'total_allocation'),
            'medical_taken': ('medical', 'taken_leaves'),
            'medical_pending': ('medical', 'pending_requests'),

            'unpaid_total': ('unpaid', 'total_allocation'),
            'unpaid_taken': ('unpaid', 'taken_leaves'),
            'unpaid_pending': ('unpaid', 'pending_requests'),

            'funeral_total': ('funeral', 'total_allocation'),
            'funeral_taken': ('funeral', 'taken_leaves'),
            'funeral_pending': ('funeral', 'pending_requests'),

            'marriage_total': ('marriage', 'total_allocation'),
            'marriage_taken': ('marriage', 'taken_leaves'),
            'marriage_pending': ('marriage', 'pending_requests'),

            'maternity_total': ('maternity', 'total_allocation'),
            'maternity_taken': ('maternity', 'taken_leaves'),
            'maternity_pending': ('maternity', 'pending_requests'),

            'paternity_total': ('paternity', 'total_allocation'),
            'paternity_taken': ('paternity', 'taken_leaves'),
            'paternity_pending': ('paternity', 'pending_requests'),
        }

        for rec in self:
            updates_by_type = {}

            # group updates per leave type
            for field, value in vals.items():
                if field in field_map:
                    leave_type_key, tracker_field = field_map[field]
                    updates_by_type.setdefault(leave_type_key, {})[tracker_field] = value

            # now apply grouped updates
            for leave_type_key, updates in updates_by_type.items():
                tracker = self.env['hr.leave.tracker'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('leave_type_name', 'ilike', f'%{leave_type_key}%'),
                    ('year', '=', year)
                ], limit=1)

                if tracker:
                    _logger.info("Updating %s tracker for %s: %s", leave_type_key, rec.employee_name, updates)
                    tracker.write(updates)
                else:
                    leave_type = self.env['hr.leave.type'].search([
                        ('name', 'ilike', f'%{leave_type_key}%')
                    ], limit=1)

                    if not leave_type:
                        _logger.warning("No leave type found for keyword '%s' when writing to %s", leave_type_key, rec.employee_name)
                        continue  # skip this type if leave_type is missing

                    values = {
                        'employee_id': rec.employee_id.id,
                        'leave_type_id': leave_type.id,
                        'year': year,
                    }
                    values.update(updates)

                    _logger.info("Creating %s tracker for %s: %s", leave_type_key, rec.employee_name, values)
                    self.env['hr.leave.tracker'].create(values)

        return True
