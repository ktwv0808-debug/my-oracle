function changeLanguage(){


let lang =
document.getElementById("language").value;



document.querySelectorAll("[data-en]").forEach(function(el){


if(lang==="ko"){


el.innerText = el.getAttribute("data-ko");


}else{


el.innerText = el.getAttribute("data-en");


}


});


}



function closePopup(){


window.open("about:blank","_self");

window.close();


}
