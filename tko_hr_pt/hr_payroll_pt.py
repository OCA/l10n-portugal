#!/usr/bin/env python
# coding: utf-8
########################################################################################
#
# Copyright (C) ThinkOpen Solutions (<http://thinkopen.solutions>). All Rights Reserved
# Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library.
#
########################################################################################

import time
from openerp import netsvc, tools
from openerp.tools.translate import _
from openerp.osv import fields, osv
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta
from math import modf
import openerp.addons.decimal_precision as dp


class hr_contract(osv.osv):
    """
    Employee contract based on the visa, work permits
    allows to configure different Salary structure
    """
    
    _history_vals_log = [{'wage':'Salario'}]

    _inherit = 'hr.contract'
    _name='hr.contract'
    _description = 'Employee Contract'
    
    def write(self, cr, uid, ids, vals, context=None):
        hr_employee_obj = self.pool.get('hr.employee')
        ir_model_obj = self.pool.get('ir.model')
        model_obj_id = ir_model_obj.search(cr, uid, [('model','=','hr.contract')])
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids):
            for value in vals:
                previous_value = self.read(cr, uid, line.id, [value])[value]
                if not any(d.has_key(value) for d in self._history_vals_log):
                    continue
                index = next(index for (index, d) in enumerate(self._history_vals_log) if d.has_key(value))
                object = self._history_vals_log[index][value]
                change = '%s - Referencia contrato %s' % (vals[value], line.name)
                hr_employee_obj.write_history_line(cr, uid, ids, line.employee_id.id, model_obj_id[0], value, object, previous_value, change, context)
            super(hr_contract, self).write(cr, uid, ids, vals, context=context)
        return True

    _columns = {
        'permit_no': fields.char('Work Permit No', size=256, required=False, readonly=False),
        'visa_no': fields.char('Visa No', size=64, required=False, readonly=False),
        'visa_expire': fields.date('Visa Expire Date'),
        'insurance_name': fields.char('Insurance', size=256, required=False, readonly=False),
        'insurance_no': fields.char('Insurance No', size=256, required=False, readonly=False),
        'meal_option': fields.selection([('cash','Cash'),('coupons', 'Meal Coupons')], 'Meal Option', required=True),
        'working_hours': fields.many2one('resource.calendar','Working Schedule', required=True),
        'no_company_ss' : fields.boolean('No Company Social Security'),
        'ss_type' : fields.many2one('hr.social.security.pt', 'Social Security Rule', required=True),

    }

class hr_employee(osv.osv):
    '''
    Employee
    '''
    
    _history_vals_log = (
                         {'job_id':'Cargo'}, 
                         {'children':'Numero de filhos'},
                         {'marital':'Estado Civil'},
                         {'handicap':'Incapacitado'},
                         {'military':'Militar'},
                         {'manager':'Gerente'},
                         {'ownership':'Titularidade IRS'},
                         {'medic_exam':'Exame Medico'}
                         )
    
    _ownership_transl = (
                         {'unique':'Casado, unico titular'},
                         {'double':'Casado, dois titulares'},
                         {'none':'Solteiro'},
                         )
    
    _marital_transl = (
                       {'single' : 'Solteiro'}, 
                       {'married' : 'Casado'}, 
                       {'widower' : 'Viuvo'}, 
                       {'divorced' : 'Divorciado'}
                       )
    _ownership = {'unique':'Casado, unico titular',
                  'double':'Casado, dois titulares',
                  'none':'Solteiro'}
                         
    
    _marital = {'single' : 'Solteiro', 
                'married' : 'Casado', 
                'widower' : 'Viuvo', 
                'divorced' : 'Divorciado'}
    
    _inherit = 'hr.employee'
    _name = 'hr.employee'
    _description = 'Employee'

    _columns = {
        'handicap': fields.boolean('Handicap', help="If is considered handicap by law"),
        'handicap_degree': fields.selection([('under_60','Under 60%'),('equal_60', 'Equal or over 60% and under 80%'),('equal_80','Equal or over 80%')], 'Handicap Degree'),
        'ownership': fields.selection([('unique','Unique'),('double','Double'),('none', 'Não definido')],'Ownership',select=True, required=True),
        'military': fields.boolean('Military', help="If is military"),
        'ssnid': fields.char('SS Identification', size=64, help="Social Security Identification of employee"),
        'history_lines': fields.one2many('hr.employee.history', 'employee_id', 'History Lines' , readonly=True),
        'income_type': fields.selection([
                                         ('A - Rendimentos do trabalho dependente','A - Rendimentos do trabalho dependente'),
                                         ('B - Rendimentos empresariais e profissionais', 'B - Rendimentos empresariais e profissionais'),
                                         ('E - Rendimentos de capitais', 'E - Rendimentos de capitais'),
                                         ('F - Rendimentos prediais', 'F - Rendimentos prediais'),
                                         ('G - Incrementos patrimoniais', 'G - Incrementos patrimoniais'),
                                         ('H - Pensões', 'H - Pensões'),
                                         ], 'Income Type', select = True, required=True),
        'nif':fields.char('Tax Identification', size=64, help="Tax Identification of employee"),
        #'bank_account_id':fields.many2one('res.partner.bank', 'Bank Account Number', domain="[('partner_id','=',partner_id)]", help="Employee bank salary account"),
    }
    _defaults = {
                 #'ownership': 'none',
                 'income_type': 'A - Rendimentos do trabalho dependente',
                 }
    
    def write(self, cr, uid, ids, vals, context=None):
        ir_model_obj = self.pool.get('ir.model')
        model_obj_id = ir_model_obj.search(cr, uid, [('model','=','hr.employee')])
        ir_model_fields_obj = self.pool.get('ir.model.fields')
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids):
            for value in vals:
                previous_value = self.read(cr, uid, line.id, [value])[value]
                if not previous_value:
                    previous_value = 'Vazio'
                if not any(d.has_key(value) for d in self._history_vals_log):
                    continue
                index = next(index for (index, d) in enumerate(self._history_vals_log) if d.has_key(value))
                object = self._history_vals_log[index][value]
                #one2many relations
                if value in ('job_id'):
                    ir_model_fields_obj_id = ir_model_fields_obj.search(cr, uid, [('model_id','=',model_obj_id[0]),('name','=',value)])
                    relation_name = ir_model_fields_obj.read(cr, uid, ir_model_fields_obj_id[0], ['relation'])['relation']
                    if vals[value]:
                        change = self.pool.get(relation_name).browse(cr, uid, vals[value]).name
                    else:
                        change = 'Vazio'
                    if previous_value and previous_value != 'Vazio':
                        previous_value =  previous_value[1]
                #selections
                elif value in('ownership','marital'):
                    if value == 'ownership':
                        dict =  self._ownership_transl
                    elif value == 'marital':
                        dict =  self._marital_transl
                    if previous_value and previous_value != 'Vazio':
                        index = next(index for (index, d) in enumerate(dict) if d.has_key(previous_value)) 
                        previous_value =  dict[index][previous_value]
                    if vals[value]: 
                        index = next(index for (index, d) in enumerate(dict) if d.has_key(vals[value]))
                        change = dict[index][vals[value]]
                    else:
                        change = 'Vazio'
                #booleans
                elif value in ('handicap','military','manager'):
                    if vals[value]:
                        change = 'Verdadeiro'
                        previous_value = 'Falso'
                    else:
                        change = 'Falso'
                        previous_value = 'Verdadeiro'
                #text fields
                else:
                    if vals[value]:
                        change = vals[value]
                    else:
                        change = 'Vazio'
                self.write_history_line(cr, uid, ids, line.id, model_obj_id[0], value, object, previous_value, change, context)
            super(hr_employee, self).write(cr, uid, ids, vals, context=context)
        return True

    def write_history_line(self, cr, uid, ids, employee_id, table, field, object_changed, data_from, data_to, context=None):
        users_obj = self.pool.get('res.users')
        history_table = self.pool.get('hr.employee.history')
        message = '%s em %s: %s mudado de %s para %s' % (
                                                            users_obj.read(cr, uid, uid, ['name'])['name'],
                                                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                            object_changed,
                                                            data_from,
                                                            data_to)
        history_table.create(cr, uid, {
                                      'employee_id' : employee_id,
                                      'message' : message,
                                      'table':table,
                                      'field':field,
                                      'from':data_from,
                                      'to':data_to,
                                      'date':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                      'user_id':uid,
                                      })
    
    def onchange_marital(self, cr, uid, ids, marital):
        result = {'value': { 'ownership': False, } }
        if not marital:
            return result
        if marital in ('single','widower','divorced'):
            result['value']['ownership'] = 'none' 
        else:
            result['value']['ownership'] = 'unique'
        return result
    
    def onchange_ownership(self, cr, uid, ids, marital, ownership):
        res = {}
        if ownership and not marital:
            raise osv.except_osv(_('Error !'), _('Cannot select ownership without the field marital selected!'))
        if ownership in ('unique','double') and marital != 'married':
            raise osv.except_osv(_('Error !'), _('Cannot select %s with marital: %s') %(self._ownership[ownership],self._marital[marital]))
        if ownership in ('none') and marital == 'married':
            raise osv.except_osv(_('Error !'), _('Cannot select %s with marital: %s') %(self._ownership[ownership],self._marital[marital]))
        return res

hr_employee()

class hr_payslip_run(osv.osv):
    _inherit = 'hr.payslip.run'
    
    def final_verify_sheet(self, cr, uid, ids, context=None):
        """
        New method to calculate the payment advice lines
        """
        slip_pool = self.pool.get('hr.payslip')
        advice_pool = self.pool.get('hr.payroll.advice')
        advice_line_pool = self.pool.get('hr.payroll.advice.line')
        sequence_pool = self.pool.get('ir.sequence')
        users_pool = self.pool.get('res.users')

        company_name = users_pool.browse(cr, uid, uid, context=context).company_id.name
        for reg in self.browse(cr, uid, ids, context=context):
            advice = {
                'name': 'Payment Advice %s' % (company_name),
                'number': sequence_pool.get(cr, uid, 'payment.advice'),
                'register_id':reg.id,
                'compute_date': date(int(reg.date_start.split('-')[0]),int(reg.date_start.split('-')[1]), 1)
            }
            pid = advice_pool.create(cr, uid, advice, context=context)

            for slip in reg.slip_ids:
                if not slip.employee_id.bank_account_id.acc_number:
                    raise osv.except_osv(_('Error !'), _('Please define bank account for the %s employee') % (slip.employee_id.name))
                value_net = [x.amount for x in slip.line_ids if
                                                            #x.slip_id.state == 'done' and 
                                                            x.salary_rule_id.category_id.code in ('NET')
                            ]
                if not value_net:
                    raise osv.except_osv(_('Error !'), _('Amount invalid for the %s employee. Category "NET" missing in payslip.') % (slip.employee_id.name))
                pline = {
                    'advice_id':pid,
                    'name':slip.employee_id.bank_account_id.acc_number,
                    'employee_id':slip.employee_id.id,
                    'amount':value_net[0],
                    #'bysal':slip.net
                }
                id = advice_line_pool.create(cr, uid, pline, context=context)
        return True
    
    def close_payslip_run(self, cr, uid, ids, context=None):
        self.final_verify_sheet(cr, uid, ids, context)
        res = super(hr_payslip_run, self).close_payslip_run(cr, uid, ids, context)
        return res 

class hr_payslip(osv.osv):
    '''
    Pay Slip
    '''

    _name = 'hr.payslip'
    _inherit = 'hr.payslip'
    _order = 'number desc'
    _columns = {
                'adhoc_rules': fields.many2many('hr.salary.rule', 'rule_adhoc_payslip', 'rule_id', 'payslip_id', 'Ad-hoc Rules', readonly=True, states={'draft': [('readonly', False)]}),
                }

    def cancel_sheet(self, cr, uid, ids, context=None):
        register_line_pool = self.pool.get('hr.contribution.register.line')
        for slip in self.browse(cr, uid, ids, context=context):
            register_line_pool.unlink(cr,uid,register_line_pool.search(cr,uid,[('payslip_id','=',slip.id)]))
        return super(hr_payslip, self).cancel_sheet(cr, uid, ids, context=context)
    
    def set_to_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'draft'}, context=context)
    #to add our own ad-hoc rules
    def get_extra_rules(self, cr, uid, payslip_id, context):
        payslip_obj = self.pool.get('hr.payslip')
        slip = payslip_obj.browse(cr, uid, payslip_id, context=context)
        return slip.adhoc_rules
    
    def process_input_lines(self, cr, uid, input_line_ids):
        pool = self.pool.get('hr.payslip.input')
        codes = set()
        for state, id, vals in input_line_ids:
            if state == 0:
                codes.add(vals['code'])
            elif state == 4:
                [input] = pool.browse(cr, uid, [id])
                codes.add(input.code)
        return codes
    
    def onchange_adhoc_rules(self, cr, uid, ids, contract_id, adhoc_rules, input_line_ids):
        if not contract_id:
            raise osv.except_osv(("Error"), ("You must select an contract first"))
        rules_pool = self.pool.get('hr.salary.rule')
        codes = self.process_input_lines(cr, uid, input_line_ids)
        [[_, _, rule_ids]] = adhoc_rules
        for rule in rules_pool.browse(cr, uid, rule_ids):
            if rule.input_ids:
                for input in rule.input_ids:
                    if input.code not in codes:
                        input_line_ids.append( (0, False, {
                                                             'name': input.name,
                                                             'code': input.code,
                                                             'contract_id': contract_id,
                                                            } ) )
                        
        return {'value': {'input_line_ids': input_line_ids}}
    
    def get_payslip_lines(self, cr, uid, contract_ids, payslip_id, lock_dict, context):
        """
        Inherit method to round amount of tax salary rule = DIR
        """
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, pool, cr, uid, employee_id, dict):
                self.pool = pool
                self.cr = cr
                self.uid = uid
                self.employee_id = employee_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""
            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(amount) as sum\
                            FROM hr_payslip as hp, hr_payslip_input as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                           (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()[0]
                return res or 0.0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""
            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours\
                            FROM hr_payslip as hp, hr_payslip_worked_days as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done'\
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                           (self.employee_id, from_date, to_date, code))
                return self.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                self.cr.execute("SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)\
                            FROM hr_payslip as hp, hr_payslip_line as pl \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s",
                            (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()
                return res and res[0] or 0.0

        #we keep a dict with the result because a value can be overwritten by another rule with the same code
        result_dict = {}
        rules = {}
        categories_dict = {}
        blacklist = []
        payslip_obj = self.pool.get('hr.payslip')
        inputs_obj = self.pool.get('hr.payslip.worked_days')
        obj_rule = self.pool.get('hr.salary.rule')
#        company_pool = self.pool.get('res.company')
        payslip = payslip_obj.browse(cr, uid, payslip_id, context=context)
        worked_days = {}
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days[worked_days_line.code] = worked_days_line
        inputs = {}
        for input_line in payslip.input_line_ids:
            inputs[input_line.code] = input_line

        categories_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, categories_dict)
        input_obj = InputLine(self.pool, cr, uid, payslip.employee_id.id, inputs)
        worked_days_obj = WorkedDays(self.pool, cr, uid, payslip.employee_id.id, worked_days)
        payslip_obj = Payslips(self.pool, cr, uid, payslip.employee_id.id, payslip)
        rules_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, rules)

        localdict = {'categories': categories_obj, 'rules': rules_obj, 'payslip': payslip_obj, 'worked_days': worked_days_obj, 'inputs': input_obj}
        #get the ids of the structures on the contracts and their parent id as well
        structure_ids = self.pool.get('hr.contract').get_all_structures(cr, uid, contract_ids, context=context)
        #get the rules of the structure and thier children
        rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(cr, uid, structure_ids, context=context)
        
        # TKO: adding adhoc rules with permission of group_adhoc_rules
        group_adhoc_rules_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tko_hr_pt', 'group_adhoc_rules')[1]
        group_adhoc_rules = self.pool.get('res.groups').browse(cr, uid, group_adhoc_rules_id, context=context)
        if group_adhoc_rules and uid in [x.id for x in group_adhoc_rules.users]:
            rules_ad_hoc = self.get_extra_rules(cr, uid, payslip_id, context=context)
            rule_ids += obj_rule._recursive_search_of_rules(cr, uid, rules_ad_hoc, context=context)
    
        #run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]

        for contract in self.pool.get('hr.contract').browse(cr, uid, contract_ids, context=context):
            employee = contract.employee_id
            localdict.update({'employee': employee, 'contract': contract})
            for rule in obj_rule.browse(cr, uid, sorted_rule_ids, context=context):
                key = rule.code + '-' + str(contract.id)
                localdict['result'] = None
                lock = False
                localdict['result_qty'] = 1.0
                #check if the rule can be applied
                if obj_rule.satisfy_condition(cr, uid, rule.id, localdict, context=context) and rule.id not in blacklist:
                    #compute the amount of the rule
                    amount, qty, rate = obj_rule.compute_rule(cr, uid, rule.id, localdict, context=context)
                    #check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    if rule.code in lock_dict:
                        #tot_rule = lock_dict[rule.code]
                        amount = lock_dict[rule.code] 
                        lock = True
                    #set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount * qty * rate / 100.0
                    # if rule is a tax deduction, round to the lowest number
                    if rule.code == 'DIR':
                        rest, tot_rule = modf(tot_rule)
                    localdict[rule.code] = tot_rule
                    rules[rule.code] = rule
                    #sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                    #create/overwrite the rule in the temporary results
                    if rule.code == 'SS' and contract.no_company_ss == False :
                        company = self.pool.get('res.company').browse(cr, uid, employee.company_id.id, context=context)
                        if contract.ss_type.emp_tax_value:
                            company_rate = (contract.ss_type.emp_tax_value * -1) + (contract.ss_type.com_tax_value * -1)
                        else:
                            company_rate = 0
                    elif rule.code =='SS' and contract.no_company_ss == True:
                        company_rate = (contract.ss_type.emp_tax_value * -1)
                    else:
                        company_rate = 0
                    result_dict[key] = {
                        'salary_rule_id': rule.id,
                        'contract_id': contract.id,
                        'name': rule.name,
                        'code': rule.code,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'appears_on_payslip': rule.appears_on_payslip,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'register_id': rule.register_id.id,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                        'company_rate' : company_rate,
                        'lock' : lock,
                    }
                else:
                    #blacklist this rule and its children
                    blacklist += [id for id, seq in self.pool.get('hr.salary.rule')._recursive_search_of_rules(cr, uid, [rule], context=context)]

        result = [value for code, value in result_dict.items()]
        return result
    
    def get_worked_day_lines(self, cr, uid, contract_ids, date_from, date_to, context=None):
        """
          Overwriten method to map the code of employee leave and count also weekends in normal working days
        """
        def was_on_leave(employee_id, datetime_day, context=None):
            res = False
            day = datetime_day.strftime("%Y-%m-%d")
            holiday_ids = self.pool.get('hr.holidays').search(cr, uid, [('state','=','validate'),('employee_id','=',employee_id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
            if holiday_ids:
                # TKO: Map leave code 
                res = { 
                       'leave_type':self.pool.get('hr.holidays').browse(cr, uid, holiday_ids, context=context)[0].holiday_status_id.name,
                       'leave_code':self.pool.get('hr.holidays').browse(cr, uid, holiday_ids, context=context)[0].holiday_status_id.code,
                }
            return res

        res = []
        for contract in self.pool.get('hr.contract').browse(cr, uid, contract_ids, context=context):
            if not contract.working_hours:
                #fill only if the contract as a working schedule linked
                continue
            attendances = {
                 'name': ("Normal Working Days paid at 100%"),
#                 'name': ("Dias trabalhados"),
                 'sequence': 1,
                 'code': 'WORK100',
                 'number_of_days': 0.0,
                 'number_of_hours': 0.0,
                 'contract_id': contract.id,
            }
            leaves = {}
            day_from = datetime.strptime(date_from,"%Y-%m-%d")
            day_to = datetime.strptime(date_to,"%Y-%m-%d")
            nb_of_days = (day_to - day_from).days + 1
            for day in range(0, nb_of_days):
                working_hours_on_day = self.pool.get('resource.calendar').working_hours_on_day(cr, uid, contract.working_hours, day_from + timedelta(days=day), context)
                if working_hours_on_day:
                    #the employee had to work
                    leave_type = was_on_leave(contract.employee_id.id, day_from + timedelta(days=day), context=context)
                    if leave_type:
                        #if he was on leave, fill the leaves dict
                        if leave_type['leave_type'] in leaves:
                            leaves[leave_type['leave_type']]['number_of_days'] += 1.0
                            leaves[leave_type['leave_type']]['number_of_hours'] += working_hours_on_day
                        else:
                            leaves[leave_type['leave_type']] = {
                                'name': leave_type['leave_type'],
                                'sequence': 5,
                                'code': leave_type['leave_code'],
                                'number_of_days': 1.0,
                                'number_of_hours': working_hours_on_day,
                                'contract_id': contract.id,
                            }
                    else:
                        #add the input vals to tmp (increment if existing)
                        attendances['number_of_days'] += 1.0
                        attendances['number_of_hours'] += working_hours_on_day
                # TKO: Extra condition to count also weekends
                else:
                    leave_type = was_on_leave(contract.employee_id.id, day_from + timedelta(days=day), context=context)
                    if leave_type:
                         if leave_type['leave_type'] in leaves:
                             leaves[leave_type['leave_type']]['number_of_days'] += 1.0
                             leaves[leave_type['leave_type']]['number_of_hours'] += leaves[leave_type['leave_type']]['number_of_hours'] / (leaves[leave_type['leave_type']]['number_of_days'] -1)
            leaves = [value for key,value in leaves.items()]
            res += [attendances] + leaves
        return res
    
    def hr_verify_sheet(self, cr, uid, ids, context=None):
        """
        This method inherit verify sheet from HR to compute contribution register lines
        """
        res = super(hr_payslip, self).hr_verify_sheet(cr, uid, ids, context)
        # TKO: Compute contribution register lines
        register_line_pool = self.pool.get('hr.contribution.register.line')
        register_pool = self.pool.get('hr.contribution.register')
        for slip in self.browse(cr, uid, ids, context=context):
            for line in slip.line_ids:
                if line.salary_rule_id.register_id:
                    company_contrib = register_pool.compute(cr, uid, line.salary_rule_id.register_id, slip, slip.contract_id, context)
                    reg_line = {
                            'name':line.name,
                            'register_id': line.salary_rule_id.register_id.id,
                            'payslip_id' : slip.id,
                            'code':line.salary_rule_id.code,
                            'employee_id':slip.employee_id.id,
                            'emp_deduction':line.total * -1,
                            'comp_deduction':company_contrib,
                            'total':line.total + line.total
                        }
                    register_line_pool.create(cr, uid, reg_line)
        return res
    
    def compute_sheet(self, cr, uid, ids, context=None):
        slip_line_pool = self.pool.get('hr.payslip.line')
        sequence_obj = self.pool.get('ir.sequence')
        lock_dict = {}
        for payslip in self.browse(cr, uid, ids, context=context):
            number = payslip.number or sequence_obj.get(cr, uid, 'salary.slip')
            #delete old payslip lines
            old_slipline_ids = slip_line_pool.search(cr, uid, [('slip_id', '=', payslip.id)], context=context)
#            old_slipline_ids
            for old_line in  slip_line_pool.browse(cr,uid,old_slipline_ids):
                if old_line.lock:
                    if old_line.salary_rule_id.protect_lock:
                        raise osv.except_osv(_('Error !'), _('A rubrica %s esta protegida não pode alterar este valor') % (old_line.name))
                
                    lock_dict[old_line.code] = old_line.amount
                slip_line_pool.unlink(cr, uid, old_line.id, context=context)
            if payslip.contract_id:
                #set the list of contract for which the rules have to be applied
                contract_ids = [payslip.contract_id.id]
            else:
                #if we don't give the contract, then the rules to apply should be for all current contracts of the employee
                contract_ids = self.get_contract(cr, uid, payslip.employee_id, payslip.date_from, payslip.date_to, context=context)
            lines = [(0,0,line) for line in self.get_payslip_lines(cr, uid, contract_ids, payslip.id,lock_dict, context=context)]
            self.write(cr, uid, [payslip.id], {'line_ids': lines, 'number': number,}, context=context)
        return True
    
    
class hr_payslip_line(osv.osv):
    _name = 'hr.payslip.line'
    _inherit = 'hr.payslip.line'
    
    
    def _calculate_total(self, cr, uid, ids, name, args, context):
        """
        Inherit method from HR Payroll to 
        """
        res = super(hr_payslip_line, self)._calculate_total(cr, uid, ids, name, args, context)
        for k,v in res.items():
            rule = self.browse(cr, uid, k)
            if rule and rule.code == 'DIR':
                ress, amount = modf(v)
                res[k] = amount
        return res
    
    _columns = {
                'total': fields.function(_calculate_total, method=True, type='float', string='Total', digits_compute=dp.get_precision('Payroll'),store=True ),
                'company_rate' : fields.float(string='Company Rate',digits_compute=dp.get_precision('Payroll')),
###
                'lock' :fields.boolean('Lock line'),
                }

hr_payslip_line()



#New class to compute the values of company contributions
class contrib_register(osv.osv):
     _name = 'hr.contribution.register'
     _inherit = 'hr.contribution.register'
     
     def _total_contrib(self, cr, uid, ids, field_names, arg, context=None):
        line_pool = self.pool.get('hr.contribution.register.line')

        res = {}
        for cur in self.browse(cr, uid, ids, context=context):
            current = line_pool.search(cr, uid, [('register_id','=',cur.id)], context=context)
            e_month = 0.0
            c_month = 0.0
            for i in line_pool.browse(cr, uid, current, context=context):
                e_month += i.emp_deduction
                c_month += i.comp_deduction
            res[cur.id]={
                'monthly_total_by_emp':e_month,
                'monthly_total_by_comp':c_month,
            }
        return res
    
     _columns = {
             'line_ids':fields.one2many('hr.contribution.register.line', 'register_id', 'Register Line', readonly=True),
             'monthly_total_by_emp': fields.function(_total_contrib, method=True, multi='dc', string='Total By Employee', digits=(16, 2)),
             'monthly_total_by_comp': fields.function(_total_contrib, method=True, multi='dc', string='Total By Company', digits=(16, 2)),
             'code':fields.char('Code', size=64, required=True, readonly=False),
             'rule_id':fields.many2one('hr.salary.rule', 'Salary Rule', required=False),
             'active':fields.boolean('Active', required=False),
             'note': fields.text('Description'),
             }
     _defaults ={
                'active': lambda *a:True,
                 }
     
     
#      def _sum_salary_rule_category(self,localdict, category, amount):
#         if category.parent_id:
#             localdict = self._sum_salary_rule_category(localdict, category.parent_id, amount)
#         localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and localdict['categories'].dict[category.code] + amount or amount
#         return localdict


     def compute(self, cr, uid, register_id, slip, contract_id, context=None):
        '''
            Compute Register Lines based on salary rules
        '''
         
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, pool, cr, uid, employee_id, dict):
                self.pool = pool
                self.cr = cr
                self.uid = uid
                self.employee_id = employee_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0
         
        obj_rule = self.pool.get('hr.salary.rule')
        blacklist = []
        categories_dict = {}
        categories_obj = BrowsableObject(self.pool, cr, uid, contract_id.employee_id.id, categories_dict)
        localdict = {'result': None, 'result_qty': 1.0,'categories' : categories_obj }
        employee = contract_id.employee_id
        tot_rule= 0.0
        localdict.update({'employee': employee, 'contract': contract_id})
        for line in slip.details_by_salary_rule_category:
            localdict.update({ line.salary_rule_id.code : line.amount})
            localdict = _sum_salary_rule_category(localdict, line.salary_rule_id.category_id,line.amount )

        #check if the rule can be applied
        if register_id.rule_id and obj_rule.satisfy_condition(cr, uid, register_id.rule_id.id, localdict, context=context) and register_id.rule_id.id not in blacklist:
            #compute the amount of the rule
            amount, qty, rate = obj_rule.compute_rule(cr, uid, register_id.rule_id.id, localdict, context=context)
            #set/overwrite the amount computed for this rule in the localdict
            tot_rule = amount * qty * rate / 100.0
        else:
            #blacklist this rule and its children
            blacklist += [id for id, seq in self.pool.get('hr.salary.rule')._recursive_search_of_rules(cr, uid, [register_id.rule_id], context=context)]
        return tot_rule


class contrib_register_line(osv.osv):
    '''
    Contribution Register Line
    Allows the computation from company contribution for some taxes
    '''

    _name = 'hr.contribution.register.line'
    _description = 'Contribution Register Line'

    def _total(self, cr, uid, ids, field_names, arg, context=None):
        res={}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.emp_deduction + line.comp_deduction
            return res

    _columns = {
        'name':fields.char('Name', size=256, required=True, readonly=False),
        'register_id': fields.many2one('hr.contribution.register', 'Register', required=False),
        'payslip_id' : fields.many2one('hr.payslip', 'Payslip'),
        'code':fields.char('Code', size=64, required=False, readonly=False),
        'employee_id':fields.many2one('hr.employee', 'Employee', required=True),
        'date': fields.date('Date'),
        'emp_deduction': fields.float('Employee Deduction', digits=(16, 2)),
        'comp_deduction': fields.float('Company Deduction', digits=(16, 2)),
        'total': fields.function(_total, method=True, store=True,  string='Total', digits=(16, 2)),
    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

class hr_salary_rule(osv.osv):
    _name = "hr.salary.rule"
    _inherit = "hr.salary.rule"
    
    _columns = {
          'register_id':fields.many2one('hr.contribution.register', 'Contribution Register', help="Eventual third party involved in the salary payment of the employees."),
          'ss_code':fields.char('Social Security Code', size=64),
          'protect_lock' : fields.boolean('Protect from lock')
    }
    
    _order = 'sequence'
    
class hr_employee_history(osv.osv):
    _name = 'hr.employee.history'
    _description = 'Employee History'
    
    _columns={
              'employee_id': fields.many2one('hr.employee', 'Employee', on_delete='cascade', required=True),
              'message': fields.char("Message", size=128, required=True),
              'table': fields.many2one('ir.model', 'Table', required=True),
              'field': fields.char("Field", size=64, required=True),
              'from': fields.char("From", size=64),
              'to': fields.char("To", size=64, required=True),
              'date' : fields.datetime("Date", required=True),
              'user_id':fields.many2one('res.users', 'User', required=True),
              }
    
hr_employee_history()

class payroll_advice(osv.osv):
    '''
    Bank Advice Note
    '''

    _name = 'hr.payroll.advice'
    _description = 'Bank Advice Note'
    _columns = {
        'register_id':fields.many2one('hr.payslip.run', 'Payslip Run', required=False),
        'name':fields.char('Name', size=2048, required=True, readonly=False),
        'note': fields.text('Description'),
        'date': fields.date('Date'),
        'compute_date': fields.date('Compute Date', required=True),
        'state':fields.selection([
            ('draft','Draft Sheet'),
            ('confirm','Confirm Sheet'),
            ('cancel','Reject'),
        ],'State', select=True, readonly=True),
        'number':fields.char('Number', size=64, required=False, readonly=True),
        'line_ids':fields.one2many('hr.payroll.advice.line', 'advice_id', 'Employee Salary', required=False),
        'chaque_nos':fields.char('Chaque Nos', size=256, required=False, readonly=False),
        'company_id':fields.many2one('res.company', 'Company', required=False),
        #'bank_id': fields.related('register_id','bank_id', type='many2one', relation='res.bank', string='Bank', help="Select the Bank Address from whcih the salary is going to be paid"),
        'bank_id': fields.many2one('res.bank', 'Bank', help="Select the Bank Address from whcih the salary is going to be paid"),
    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'state': lambda *a: 'draft',
        'company_id': lambda self, cr, uid, context: \
                self.pool.get('res.users').browse(cr, uid, uid,
                    context=context).company_id.id,
    }

    def confirm_sheet(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'confirm'}, context=context)
        return True

    def set_to_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'}, context=context)
        return True
    
    

    def cancel_sheet(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cancel'}, context=context)
        return True

    def onchange_company_id(self, cr, uid, ids, company_id=False, context=None):
        res = {}
        if company_id:
            company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
            if company.partner_id.bank_ids:
                res.update({'bank': company.partner_id.bank_ids[0].bank.name})
        return {
            'value':res
        }
        
        
        
    def compute_sheet(self, cr, uid, ids, context=None):
        emp_pool = self.pool.get('hr.employee')
        slip_pool = self.pool.get('hr.payslip')
        slip_line_pool = self.pool.get('hr.payslip.line')
        advice_line_pool = self.pool.get('hr.payroll.advice.line')
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids):
            #remove old lines
            advice_line_pool.unlink(cr, uid, [x.id for x in line.line_ids])
            #compute new lines
            compute_date_year, compute_date_month, compute_date_day = line.compute_date.split('-')
            start_date = date(int(compute_date_year), int(compute_date_month), 1)
            if compute_date_month < 12:
                end_date =  date(int(compute_date_year), int(compute_date_month) + 1 , 1)
            else:
                end_date =  date(int(compute_date_year) + 1, 1, 1)
            payslip_ids = slip_pool.search(cr, uid, [
                                                     ('date_from','>=',str(start_date))
                                                     ,('date_from','<',str(end_date))
                                                     ], order = 'employee_id')
            payslips = slip_pool.browse(cr, uid, payslip_ids)
            for payslip in payslips:
                if not payslip.employee_id.bank_account_id.acc_number:
                    raise osv.except_osv(_('Error !'), _('Please define bank account for the %s employee') % (payslip.employee_id.name))
                value_net = [x.amount for x in payslip.line_ids if
                                                            x.slip_id.state == 'done'
                                                            and x.salary_rule_id.category_id.code in ('NET')
                            ]
                if not value_net:
                    raise osv.except_osv(_('Error !'), _('Amount invalid for the %s employee. Category "NET" missing in payslip.') % (payslip.employee_id.name))
                vals = {
                         'advice_id': line.id,
                         'name':payslip.employee_id.bank_account_id.acc_number,
                         'employee_id':payslip.employee_id.id,
                         'amount': value_net[0],
                         #'bysal': payslip.net
                         #'flag': ',
                        }
                advice_line_pool.create(cr, uid, vals)
        return True

class payroll_advice_line(osv.osv):
    '''
    Bank Advice Lines
    '''

    _name = 'hr.payroll.advice.line'
    _description = 'Bank Advice Lines'
    _columns = {
        'advice_id':fields.many2one('hr.payroll.advice', 'Bank Advice', required=False),
        'name':fields.char('Bank Account A/C', size=64, required=True, readonly=False),
        'employee_id':fields.many2one('hr.employee', 'Employee', required=True),
        'amount': fields.float('Amount', digits=(16, 2)),
    }
    
    def onchange_employee_id(self, cr, uid, ids, date, employee_id):
        res = {}
        if employee_id:
            employee = self.pool.get('hr.employee').browse(cr, uid, employee_id)
            if not employee.bank_account_id.acc_number:
                    raise osv.except_osv(_('Error !'), _('Please define bank account for the %s employee') % (employee.name))
            else:
                res.update({'name': employee.bank_account_id.acc_number})
        return {'value': res}
    
class hr_social_security_pt(osv.osv):
    _name = 'hr.social.security.pt'
    _columns = {
        'name': fields.char('Sequence', size=512, required=False, readonly=True),
        'emp_tax_value' : fields.float(string='Employee Tax', digits_compute=dp.get_precision('Account'), readonly=True),
        'com_tax_value' : fields.float(string='Company Tax', digits_compute=dp.get_precision('Account'), readonly=True),
    }