/**
 * ORYA Voice — Reconnaissance vocale + TTS multilingue
 * Orange Tunisie PFE 2026
 * Fonctionne avec le chatbot existant (chatbot.js)
 */

(function () {
    'use strict';

    var currentLang = 'fr-FR'; // Uniquement français
    var speakEnabled = localStorage.getItem('orya-speak') !== 'false';
    var isListening = false;
    var recognition = null;
    var synthesis = window.speechSynthesis;

    var LANG_LABELS = {
        'fr-FR': 'Francais',
        'ar-TN': 'عربي',
        'en-US': 'English'
    };

    // ===== INIT LANGUE =====
    function initLang() {
        var sel = document.getElementById('orya-language');
        var lbl = document.getElementById('orya-lang-label');
        if (sel) sel.value = currentLang;
        if (lbl) lbl.textContent = LANG_LABELS[currentLang] || currentLang;
    }

    window.onLangChange = function (lang) {
        currentLang = lang;
        localStorage.setItem('orya-lang', lang);
        var lbl = document.getElementById('orya-lang-label');
        if (lbl) lbl.textContent = LANG_LABELS[lang] || lang;
        if (recognition) recognition.lang = lang;

        var confirmMsg = {
            'fr-FR': 'Langue changee en francais.',
            'ar-TN': 'تم التغيير إلى العربية.',
            'en-US': 'Language changed to English.'
        };
        // Injecter un message dans le chat via la fonction existante
        if (window.appendMessage) {
            window.appendMessage('assistant', confirmMsg[lang] || confirmMsg['fr-FR']);
        }
    };

    // ===== RECONNAISSANCE VOCALE =====
    function initRecognition() {
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            var btn = document.getElementById('orya-mic-btn');
            if (btn) { btn.style.display = 'none'; }
            return;
        }

        recognition = new SR();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = currentLang;

        recognition.onresult = function (e) {
            var transcript = e.results[0][0].transcript;
            var input = document.getElementById('chatbot-input');
            if (input) {
                input.value = transcript;
                // Declenchement auto
                var form = document.getElementById('chatbot-form');
                if (form) form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            }
            stopListening();
        };

        recognition.onerror = function (e) {
            console.warn('[ORYA Voice]', e.error);
            stopListening();
        };

        recognition.onend = function () {
            stopListening();
        };
    }

    window.oryaToggleVoice = function () {
        if (!recognition) {
            alert('Reconnaissance vocale non disponible. Utilisez Chrome.');
            return;
        }
        if (isListening) {
            recognition.stop();
            stopListening();
        } else {
            startListening();
        }
    };

    function startListening() {
        isListening = true;
        recognition.lang = currentLang;
        recognition.start();

        var indicator = document.getElementById('orya-listening');
        var btn = document.getElementById('orya-mic-btn');
        if (indicator) indicator.style.display = 'flex';
        if (btn) btn.classList.add('active');
    }

    function stopListening() {
        isListening = false;
        var indicator = document.getElementById('orya-listening');
        var btn = document.getElementById('orya-mic-btn');
        if (indicator) indicator.style.display = 'none';
        if (btn) btn.classList.remove('active');
    }

    // ===== TTS — LECTURE VOCALE =====
    window.oryaSpeak = function (text) {
        if (!speakEnabled || !synthesis || !text) return;
        synthesis.cancel();
        var utt = new SpeechSynthesisUtterance(text);
        utt.lang = currentLang;
        utt.rate = 0.95;
        utt.pitch = 1.0;

        // Choisir la voix correspondante si dispo
        var voices = synthesis.getVoices();
        var langCode = currentLang.split('-')[0];
        var match = voices.find(function (v) { return v.lang.startsWith(langCode); });
        if (match) utt.voice = match;

        synthesis.speak(utt);
    };

    // Patch : intercepter les reponses du chatbot existant pour les lire
    function patchChatbotForTTS() {
        // On attend que chatbot.js ait charge appendMessage
        var tries = 0;
        var iv = setInterval(function () {
            tries++;
            if (tries > 20) { clearInterval(iv); return; }

            var orig = window.appendMessage;
            if (typeof orig === 'function') {
                clearInterval(iv);
                window.appendMessage = function (role, content, meta) {
                    orig(role, content, meta);
                    // Lire les reponses de l'assistant a voix haute
                    if (role === 'assistant' && speakEnabled) {
                        // Extraire le texte pur (sans HTML)
                        var tmp = document.createElement('div');
                        tmp.innerHTML = content;
                        var plainText = (tmp.textContent || tmp.innerText || '').trim();
                        if (plainText.length < 300) {
                            window.oryaSpeak(plainText);
                        }
                    }
                };
            }
        }, 300);
    }

    // ===== INIT =====
    document.addEventListener('DOMContentLoaded', function () {
        initLang();
        initRecognition();
        patchChatbotForTTS();

        // Raccourci Ctrl+M pour micro
        document.addEventListener('keydown', function (e) {
            if (e.ctrlKey && e.key === 'm') {
                e.preventDefault();
                window.oryaToggleVoice();
            }
        });
    });

})();
