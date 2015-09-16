frappe.require("assets/frappe/js/lib/jquery/jquery.ui.min.js");
frappe.require("/assets/phr/js/jquery.autocomplete.multiselect.js");

window.disable_signup = {{ disable_signup and "true" or "false" }};

window.login = {};

login.bind_events = function() {
	if(!window.pageInitialized){
		$(window).on("hashchange", function() {
			login.route();
		});

		$(".form-login").on("submit", function(event) {
			event.preventDefault();
			$('.btn-primary').prop("disabled", true);
			var args = {};
			args.cmd = "login";
			if(window.location.hash == "#patient"){
				args.usr = ($("#patient_login_email").val() || "").trim();
				args.pwd = $("#patient_login_password").val();
				args.login_as = "Patient";
			}
			else{
				args.usr = ($("#provider_login_email").val() || "").trim();
				args.pwd = $("#provider_login_password").val();
				args.login_as = "Provider";
			}
			if(!args.usr || !args.pwd) {
				frappe.msgprint(__("Both login and password required"));
				return false;
			}
			login.call(args);
		});

		$(".form-signup").unbind("submit").submit(function(event) {
			event.preventDefault();
			$('.btn-primary').prop("disabled", true);
			var args = {};
			args.first_name = ($("#signup_firstname").val() || "").trim();
			args.middle_name = ($("#signup_middlename").val() || "").trim();
			args.last_name = ($("#signup_lastname").val() || "").trim();
			args.email_id = ($("#signup_email").val() || "").trim();
			cnf_email_id = ($("#signup_email_cnf").val() || "").trim();
			args.contact = ($("#signup_contact").val() || "").trim();
			cnf_contact = ($("#signup_contact_cnf").val() || "").trim();
			args.created_via="Desktop";

			// check if user is provider or patient
			var route = window.location.hash.slice(1);
			if (route == "provider-signup"){
				args.is_provider = true;
				args.gender = ($("#gender option:selected").val() || "").trim();
				args.registration_number = ($("#medical_reg_number").val() || "").trim();
				args.specialization= ($("#provider_specialization").val() || "").trim();
			}

			args.cmd = "phr.templates.pages.login.create_profile";

			if (!/^[0-9]+$/.test(args.contact) || !/^[0-9]+$/.test(cnf_contact)){
				frappe.msgprint(__("Valid contact number required"));
				$('.btn-primary').prop("disabled", false);
				return false;
			}
			if(!args.email_id || !valid_email(args.email_id) || !valid_email(cnf_email_id)) {
				frappe.msgprint(__("Valid email and name required"));
				$('.btn-primary').prop("disabled", false);
				return false;
			}
			else if(args.email_id != cnf_email_id){
				frappe.msgprint(__("Email Addresses doesn't match"));
				$('.btn-primary').prop("disabled", false);
				return false;
			}
			else if(args.contact != cnf_contact){
				frappe.msgprint(__("Contact Nos doesn't match"));
				$('.btn-primary').prop("disabled", false);
				return false;
			}
			// TODO medical registion number validations
			login.call(args);
		});

		$(".form-forgot").on("submit", function(event) {
			event.preventDefault();
			$('.btn-primary').prop("disabled", true);
			var args = {};
			args.cmd = "phr.templates.pages.login.reset_password";
			args.user = ($("#forgot_email").val() || "").trim();
			if(!args.user) {
				frappe.msgprint(__("Valid Login id required."));
				return false;
			}
			login.call(args);
		});
	}
}

clear_credentials=function(){
	$("#patient_login_email").val("");
	$("#patient_login_password").val("");
	$("#provider_login_email").val("");
	$("#provider_login_password").val("");
}

login.route = function() {
	var route = window.location.hash.slice(1);
	if(!route) route = "login";
	else if(route == "patient-signup") route = "signup";
	else if(route == "provider-signup") route = "provider_signup";
	clear_credentials();
	login[route]();
}

login.login = function() {
	$("form").toggle(false);
	$(".form-login").toggle(true);
}

login.forgot = function() {
	$("form").toggle(false);
	$(".form-forgot").toggle(true);
}

login.signup = function() {
	$("form").toggle(false);
	// patient sigup, hiding the provider fields
	$("#gender").addClass("hide");
	$("#provider_registration_number").addClass("hide");
	$("#specialization").addClass("hide");
	// set fields to required false
	$("#medical_reg_number").prop("required", false);
	$("#provider_specialization").prop("required", false);
	// removing all the child element from redirect-url and appending new redirect
	// URL for patient >> #patient
	$("#redirect-url").empty();
	$("<p>Already have an account?<a href='#patient' id='redirect-login'>Log-in\
	</a></p>").appendTo($("#redirect-url"))

	$(".form-signup").toggle(true);
	$(".form-signup").trigger("reset");
}

login.provider_signup = function(){
	$("form").toggle(false);
	// provider sigup, unhiding the provider fields
	$("#gender").removeClass("hide");
	$("#provider_registration_number").removeClass("hide");
	$("#specialization").removeClass("hide");
	// set fields to required
	$("#medical_reg_number").prop("required", true);
	$("#provider_specialization").prop("required", true);
	// removing all the child element from redirect-url and appending new redirect
	// URL for patient >> #provider
	$("#redirect-url").empty();
	$("<p>Already have an account?<a href='#provider' id='redirect-login'>Log-in\
	</a></p>").appendTo($("#redirect-url"))

	$(".form-signup").toggle(true);
	$(".form-signup").trigger("reset");
}

login.patient = function() {
	$("form").toggle(false);
	$(".patient-login").toggle(true);
	// resetting provider & patient login form
	$(".provider-login").trigger("reset");
	$(".patient-login").trigger("reset");

	$("#provider").removeClass("active");
	$("#li-provider").removeClass("active");
	$("#patient").addClass("active");
	$("#li-patient").addClass("active");
}

login.provider = function() {
	$("form").toggle(false);
	$(".provider-login").toggle(true);
	// resetting provider & patient login form
	$(".patient-login").trigger("reset");
	$(".provider-login").trigger("reset");

	$("#patient").removeClass("active");
	$("#li-patient").removeClass("active");
	$("#provider").addClass("active");
	$("#li-provider").addClass("active");
}

// Login
login.call = function(args) {
	$('.btn-primary').prop("disabled", true);
	$.ajax({
		type: "POST",
		url: "/",
		data: args,
		dataType: "json",
		statusCode: login.login_handlers
	}).always(function(){
		$('.btn-primary').prop("disabled", false);
	})
}

login.login_handlers = (function() {
	var get_error_handler = function(default_message) {
		return function(xhr, data) {
			if(xhr.responseJSON) {
				data = xhr.responseJSON;
			}

			var message = data._server_messages
				? JSON.parse(data._server_messages).join("\n") : default_message;
			frappe.msgprint(message);
		};
	}

	var login_handlers = {
		200: function(data) {
            if(data.message=="Logged In") {
				window.location.href = get_url_arg("redirect-to") || "/desk";
			} else if(data.message=="No App") {
				var url='';
				if (data.mob_v_req && data.mob_v_req=='Yes'){
					url='/verify_mobile?id='+frappe.get_cookie("profile_id")
				}
				if(localStorage) {
					var last_visited =
						localStorage.getItem("last_visited")
							|| get_url_arg("redirect-to")
							|| url
							|| data.access_link || "/index";
					localStorage.removeItem("last_visited");
					window.location.href = last_visited;
					sessionStorage.setItem("pid",frappe.get_cookie("profile_id"));
					sessionStorage.setItem("cid",frappe.get_cookie("profile_id"));
				} else {

					go_to_url= url || data.access_link || "/index"
					window.location.href = "/index";
				}
			} else if(["#patient-signup", "#provider-signup", "#forgot"].indexOf(window.location.hash)!==-1) {
				if (data.message["returncode"]==101){
					frappe.msgprint(data.message.msg_display);
					if(window.location.hash == "#patient-signup")
						setTimeout("window.location.href = '/login#patient'", 5000);
					else if (window.location.hash == "#provider-signup")
						setTimeout("window.location.href = '/login#provider'", 5000);
					else
						setTimeout("window.location.href = '/login'", 5000);
				}
				else{
					frappe.msgprint(data.message.msg_display);
				}


			}
		},
		401: get_error_handler(__("Invalid Login")),
		417: get_error_handler(__("Oops! Something went wrong"))
	};

	return login_handlers;
})();

frappe.ready(function() {
	if(!window.pageInitialized){
		// window.location.hash = "login";
		window.location.hash = "patient";
		login.bind_events();
		window.pageInitialized = true;
		login.login();
		$(".form-signup, .form-forgot").removeClass("hide");
		$(document).trigger('login_rendered');
	}
});
