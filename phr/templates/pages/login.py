from __future__ import unicode_literals
import frappe
from frappe.utils import cint, now, get_gravatar
from frappe import throw, msgprint, _
from frappe.auth import _update_password
from frappe.core.doctype.notification_count.notification_count import clear_notifications
import frappe.permissions
import json
from frappe import _
import barcode
import time
import os
from phr.templates.pages.utils import get_base_url
from frappe.utils import cint, flt, now, cstr, strip_html
import random
import string
STANDARD_USERS = ("Guest", "Administrator")


@frappe.whitelist(allow_guest=True)
# def create_profile(first_name,middle_name,last_name,email_id,contact,created_via):
def create_profile(first_name,middle_name,last_name,email_id,contact,created_via, is_provider=False, gender="Male", registration_number=None, specialization=None):
	"""
		1.Create Profile in Core PHR(Solr)
		2.When Successful Create Profile  in ERPNext
		3.After Successful Profile Creation genarate link
		4.Complete Registration
	"""
	from phr.templates.pages.profile import not_duplicate_contact

	if not not_duplicate_contact(contact,email_id):
		return {"returncode" : 409, "message_summary":"Contact Already Used.","msg_display":"Contact Already Used."}

	user = frappe.db.get("User", {"email": email_id})
	if user:
		if user.disabled:
			return {"returncode" : 410, "message_summary":"Registered but disabled.","msg_display":"Registered but disabled."}
		else:
			return {"returncode" : 409, "message_summary" : "Already Registered","msg_display":"Already Registered"}
	else:
		if not is_provider:
			barcode = get_barcode()
			args = {
			    'person_firstname': first_name,
			    'person_middlename': middle_name,
			    'person_lastname': last_name,
			    'email': email_id,
			    'mobile': contact,
			    'received_from': created_via,
			    'provider': 'false',
			    "barcode": str(barcode)
			}
			# return args
			profile_res = create_profile_in_solr(args)
			response = json.loads(profile_res)
			if response['returncode']==101:
				path = get_image_path(barcode,response['entityid'])
				file_path = '/files/'+response['entityid']+'/'+response['entityid']+".svg"
				res = create_profile_in_db(response['entityid'],args,response,file_path)
				db = set_default_dashboard(response['entityid'])
				if res.get("returncode") == 101:
					response['msg_display']='Profile created successfully, please check your email and complete signup process'
					return response
				else:
					return res
			else:
				return response
		else:
			try:
				# check if provider already exists
				if not is_exisiting_provider(email_id, contact):
					# check for valid specialization
					if not frappe.db.get_value("Specialization", specialization, 'name'):
						return {
							"returncode" : 409,
							"message_summary":"Invalid Specialization Detail",
							"msg_display":"Invalid Specialization Detail '%s'"%specialization
						}

					# create new Provider document
					provider_name = "%s %s %s"%(first_name,middle_name, last_name)
					doc = frappe.get_doc({
							"doctype":"Provider",
							"provider_name":provider_name,
							"provider_category": "TieUp",
							"specialization": specialization,
							"mobile_number": contact,
							"email": email_id,
							"received_from": created_via,
							"gender":gender,
							"reg_no": registration_number
						})
					doc.ignore_permissions = True
					doc.save()
					return {
						"returncode" : 101,
						"message_summary":"Registration Details Emailed.",
						"msg_display":"Registration Details Emailed."
					}
				else:
					return {
						"returncode" : 409,
						"message_summary" : "Provider is Already Registered",
						"msg_display":"Provider is Already Registered"
					}
			except Exception, e:
				import traceback
				print "login.py",e, "\n",traceback.format_exc()
				return {
					"returncode" : 101,
					"message_summary" : "Can not register at this moment, Please try after some time",
					"msg_display":"Can not register at this moment, Please try after some time"
				}

def is_exisiting_provider(email, mobile_number):
	query = """SELECT count(name) FROM `tabProvider` WHERE email='%s' OR
			mobile_number='%s'"""%(email, mobile_number)

	if frappe.db.sql(query, as_list=True)[0][0] > 0:
		return True
	else:
		return False

@frappe.whitelist(allow_guest=True)
def set_default_dashboard(profile_id):
	sr = frappe.get_doc({
		"doctype":"Shortcut",
		"profile_id":profile_id,
		"created_via": "Web",
		"visits":1,
		"medications":1,
		"disease_monitoring":1,
		"events":1
	})
	sr.ignore_permissions = True
	sr.insert()


@frappe.whitelist(allow_guest=True)
def get_barcode():
	barcode.PROVIDED_BARCODES
	EAN = barcode.get_barcode_class('ean13')
	m = str(int(round(time.time() * 1000)))
	ean = EAN(m)
	return ean

@frappe.whitelist(allow_guest=True)
def get_image_path(ean,entityid):
	path = get_path(entityid)
	ean.writer.set_options({"module_height":6.0})
	fullname = ean.save(path)
	return fullname

@frappe.whitelist(allow_guest=True)
def get_path(entityid):
	site_name = get_site_name()
	path = os.path.abspath(os.path.join('.',site_name, 'public', 'files'))
	directory = '/%s/%s/'%(path,entityid)
	if not os.path.exists(directory):
		os.makedirs(directory)

	if directory:
		filepath = directory+entityid
	return filepath or None

@frappe.whitelist(allow_guest=True)
def get_site_name():
       return frappe.local.site_path.split('/')[1]


@frappe.whitelist(allow_guest=True)
def create_profile_in_db(id, args, response, path=None):
	from frappe.utils import random_string
	password = random_string(10)
	user = frappe.get_doc({
		"doctype":"User",
		"email": args["email"],
		"profile_id":id,
		"first_name": args["person_firstname"],
		"middle_name": args["person_middlename"],
		"last_name": args["person_lastname"],
		"enabled": 1,
		"user_image": args.get('user_image'),
		"contact":args["mobile"],
		"new_password": password,
		"user_type": "Website User",
		"access_type":"Patient",
		"barcode":path,
		"created_via":args["received_from"],
		"password_str":password
	})
	user.ignore_permissions = True
	user.no_welcome_mail = True
	user.insert()
	# notify = notify_user(response,args,id)
	# return _("Registration Details Emailed.")
	return notify_user(response,args,id)

"""
	Send Welcome Mail to User
"""
@frappe.whitelist(allow_guest=True)
def notify_user(res_data, user_args, profile_id, send_sms=True, is_provider=False):
	"""
		res_data = profile response from Solr
		user_args = arguments that are sent to createProfile Service of Solr
		profile_id = new user's profile id
	"""
	from frappe.utils import random_string
	new_password = random_string(10)
	_update_password(user_args["email"], new_password)
	db_set(user_args,"password_str",new_password)
	return send_welcome_mail(new_password,profile_id,user_args, send_sms, is_provider)

"""
	Set values of str_password
"""
@frappe.whitelist(allow_guest=True)
def db_set(args,fieldname, value):
	#args.set(fieldname, value)
	args["modified"] = now()
	args["modified_by"] = frappe.session.user
	frappe.db.set_value("User", args["email"], fieldname, value, args["modified"], args["modified_by"])

"""
	Send Mail and SMS to User
"""
@frappe.whitelist(allow_guest=True)
def send_welcome_mail(password,profile_id,args, send_sms=True, is_provider=False):
	from frappe.utils import random_string, get_url
	key = random_string(32)
	db_set(args,"reset_password_key", key)
	link = get_url("/verify_email?id="+profile_id+"&key=" + key)

	mob_code = get_mob_code()
	update_verification_details(args,password,key,mob_code,link,profile_id, is_provider)
	mail_response = send_login_mail(args,"Verify Your Account", "templates/emails/new_user.html", {"link": link,"password":password,"verify_sms":send_sms})

	if send_sms:
		mob_already_v = frappe.db.get_value("Mobile Verification",{"mobile_no":args["mobile"],"mflag":1},"name")
		if not mob_already_v:
			from phr.templates.pages.profile import make_mobile_verification_entry
			if not frappe.db.get_value("Mobile Verification",{"mobile_no":args["mobile"]},"name"):
				make_mobile_verification_entry(args["mobile"],profile_id,mob_code)
			else:
				pass

			from phr.templates.pages.utils import get_sms_template
			sms = get_sms_template("registration",{ "mobile_code": mob_code })
			rec_list = []
			rec_list.append(args["mobile"])
			from erpnext.setup.doctype.sms_settings.sms_settings import send_sms
			send_sms(rec_list,sms)
		elif mob_already_v:
			vd = frappe.get_doc("Verification Details",profile_id)
			vd.mflag = 1
			vd.save(ignore_permissions=True)

	return mail_response

@frappe.whitelist(allow_guest=True)
def get_mob_code():
	return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(6))


def update_verification_details(args,password,key,mob_code,link,profile_id, is_provider=False):
	vd = frappe.get_doc({
		"doctype":"Verification Details",
		"profile_id":profile_id,
		"email": args["email"],
		"mobile_no": args["mobile"],
		"hash": key,
		"verification_link": link,
		"temp_password": password,
		"mobile_verification_code":mob_code,
		"verification_for": "Provider" if is_provider else "Patient"
	})
	vd.ignore_permissions = True
	vd.insert()

	return vd.name

def send_login_mail(user_args, subject, template, add_args):
	"""send mail with login details"""
	from frappe.utils.user import get_user_fullname
	from frappe.utils import get_url
	try:
		mail_titles = frappe.get_hooks().get("login_mail_title", [])
		title = frappe.db.get_default('company') or (mail_titles and mail_titles[0]) or ""

		full_name = get_user_fullname(frappe.session['user'])
		if full_name == "Guest":
			full_name = "Administrator"

		args = {
			'first_name': user_args["person_firstname"] or user_args["person_lastname"] or "user",
			'user': user_args["email"],
			'title': title,
			'login_url': get_url(),
			'user_fullname': full_name
		}

		args.update(add_args)

		sender = frappe.session.user not in STANDARD_USERS and frappe.session.user or None

		frappe.sendmail(recipients=user_args["email"], sender=sender, subject=subject,
			message=frappe.get_template(template).render(args))
		return {
			"returncode" : 101,
			"message_summary":"Registration Details Emailed.",
			"msg_display":"Registration Details Emailed."
		}
	except Exception, e:
		import traceback
		print "notify", traceback.format_exc()
		frappe.db.rollback()
		return {
			"returncode" : 501,
			"message_summary":"Outgoing Email Server is not configured, Please Contact Administrator.",
			"msg_display":"Outgoing Email Server is not configured, Please Contact Administrator."
		}

def create_profile_in_solr(args):
	request_type="POST"
	url = "%s/createProfile"%get_base_url()
	data=json.dumps(args)
	from phr.phr.phr_api import get_response
	response=get_response(url,data,request_type)
	return response.text

@frappe.whitelist(allow_guest=True)
def reset_password(user):
	if user=="Administrator":
		return _("Not allowed to reset the password of {0}").format(user)
	try:
		user = frappe.get_doc("User", user)
		user.validate_reset_password()
		user.reset_password()
		return {"returncode":101,"msg_display":"Password reset instructions have been sent to your email"}
	except frappe.DoesNotExistError:
		msg="""User %s does not exist"""%user
		return {"returncode":401,"msg_display":msg}
		#return _("User {0} does not exist").format(user)

def user_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.widgets.reportview import get_match_cond
	txt = "%{}%".format(txt)
	return frappe.db.sql("""select name, concat_ws(' ', first_name, middle_name, last_name)
		from `tabUser`
		where ifnull(enabled, 0)=1
			and docstatus < 2
			and name not in ({standard_users})
			and user_type != 'Website User'
			and ({key} like %s
				or concat_ws(' ', first_name, middle_name, last_name) like %s)
			{mcond}
		order by
			case when name like %s then 0 else 1 end,
			case when concat_ws(' ', first_name, middle_name, last_name) like %s
				then 0 else 1 end,
			name asc
		limit %s, %s""".format(standard_users=", ".join(["%s"]*len(STANDARD_USERS)),
			key=searchfield, mcond=get_match_cond(doctype)),
			tuple(list(STANDARD_USERS) + [txt, txt, txt, txt, start, page_len]))

def get_total_users(exclude_users=None):
	"""Returns total no. of system users"""
	return len(get_system_users(exclude_users=exclude_users))

def get_system_users(exclude_users=None):
	if not exclude_users:
		exclude_users = []
	elif not isinstance(exclude_users, (list, tuple)):
		exclude_users = [exclude_users]

	exclude_users += list(STANDARD_USERS)

	system_users = frappe.db.sql_list("""select name from `tabUser`
		where enabled=1 and user_type != 'Website User'
		and name not in ({})""".format(", ".join(["%s"]*len(exclude_users))),
		exclude_users)

	return system_users

def get_active_users():
	"""Returns No. of system users who logged in, in the last 3 days"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type != 'Website User'
		and name not in ({})
		and hour(timediff(now(), last_login)) < 72""".format(", ".join(["%s"]*len(STANDARD_USERS))), STANDARD_USERS)[0][0]

def get_website_users():
	"""Returns total no. of website users"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type = 'Website User'""")[0][0]

def get_active_website_users():
	"""Returns No. of website users who logged in, in the last 3 days"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type = 'Website User'
		and hour(timediff(now(), last_login)) < 72""")[0][0]

def get_permission_query_conditions(user):
	if user=="Administrator":
		return ""

	else:
		return """(`tabUser`.name not in ({standard_users}))""".format(
			standard_users='"' + '", "'.join(STANDARD_USERS) + '"')

def has_permission(doc, user):
	if (user != "Administrator") and (doc.name in STANDARD_USERS):
		# dont allow non Administrator user to view / edit Administrator user
		return False

	else:
		return True
