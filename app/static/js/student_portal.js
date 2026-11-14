(() => {
"use strict";
const token=document.querySelector('meta[name="csrf-token"]')?.content||"";
const message=document.getElementById("studentRegistrationMessage");
document.querySelectorAll("[data-cancel-registration]").forEach(button=>{
button.addEventListener("click",async()=>{
const eventId=button.dataset.cancelRegistration;
if(!window.confirm("Cancel your registration for this event?"))return;
button.disabled=true;
if(message)message.textContent="Cancelling registration…";
try{
const response=await fetch(`/api/registrations/${eventId}`,{method:"DELETE",credentials:"same-origin",headers:{"X-CSRFToken":token}});
const data=await response.json().catch(()=>({}));
if(!response.ok)throw new Error(data.error||"Could not cancel registration.");
if(message){message.textContent=data.message||"Registration cancelled.";message.className="portal-success";}
window.location.reload();
}catch(error){if(message){message.textContent=error.message;message.className="portal-error";}button.disabled=false;}
});
});
})();
