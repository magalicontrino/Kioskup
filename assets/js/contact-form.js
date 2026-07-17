/* Envoi du formulaire de contact via le logiciel de mail du visiteur.
 *
 * Webflow gérait la soumission depuis son propre backend ; hors de son
 * hébergement le formulaire partait dans le vide. Faute de backend, on ouvre un
 * brouillon pré-rempli chez le visiteur et on réutilise les blocs de message
 * d'origine (.w-form-done / .w-form-fail) : le design reste intact.
 */
(function () {
  "use strict";

  var DESTINATAIRE = "kioskup.bxl@gmail.com";

  var form = document.getElementById("wf-form-Formulaire-contact");
  if (!form) return;

  var wrap = form.closest(".w-form");
  var done = wrap && wrap.querySelector(".w-form-done");
  var fail = wrap && wrap.querySelector(".w-form-fail");

  function texte(el, message) {
    if (!el) return;
    var slot = el.firstElementChild || el;
    slot.textContent = message;
  }

  // Le message n'est que pré-rempli : annoncer un envoi effectif serait faux.
  if (done) {
    texte(
      done,
      "Votre message s’ouvre dans votre logiciel de mail. Cliquez sur « Envoyer » pour nous le faire parvenir."
    );
  }

  // Capture : webflow.js écoute en phase de bouillonnement et enverrait le
  // formulaire à l'API Webflow. On l'intercepte donc avant lui.
  form.addEventListener(
    "submit",
    function (e) {
      e.preventDefault();
      e.stopPropagation();

      var nom = form.querySelector("#name").value.trim();
      var email = form.querySelector("#email").value.trim();
      var message = form.querySelector("#field").value.trim();

      var corps =
        "Nom : " + nom + "\n" + "Email : " + email + "\n\n" + message + "\n";

      var lien =
        "mailto:" +
        DESTINATAIRE +
        "?subject=" +
        encodeURIComponent("Contact Kioskup — " + nom) +
        "&body=" +
        encodeURIComponent(corps);

      // Un mailto trop long est tronqué, voire ignoré, par certains clients.
      if (lien.length > 1900) {
        texte(
          fail,
          "Votre message est trop long. Raccourcissez-le ou écrivez-nous directement à " +
            DESTINATAIRE +
            "."
        );
        if (fail) fail.style.display = "block";
        return;
      }

      if (fail) fail.style.display = "none";
      window.location.href = lien;

      form.style.display = "none";
      if (done) done.style.display = "block";
    },
    true
  );
})();
