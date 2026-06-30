const translations = {


en:{


save:"Save ETH Price",

history:"Price History",

signal:"Auto Trading Signal",

trades:"Trading Records",

whitepaper:"W-donation Whitepaper",

poem:"Toward Victory",

mission:"Our Mission",

close:"Close"


},



ko:{


save:"ETH 가격 저장",

history:"가격 기록",

signal:"자동 거래 신호",

trades:"거래 기록",

whitepaper:"W-donation 백서",

poem:"승리를 향하여",

mission:"우리의 사명",

close:"닫기"


}


};



function changeLanguage(){


let lang =
document.getElementById("language").value;



document.querySelectorAll("[data-lang]").forEach(function(item){


item.innerHTML =
translations[lang][item.dataset.lang];


});


}
