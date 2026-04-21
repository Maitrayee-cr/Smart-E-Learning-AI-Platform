document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('ui-ready');
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const getCookie = (name) => {
        const cookieValue = document.cookie
            .split('; ')
            .find((row) => row.startsWith(name + '='));
        return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : null;
    };

    const getCsrfToken = () => getCookie('csrftoken') || csrfInput?.value || '';

    const syncCsrfTokenForForms = () => {
        const csrfToken = getCsrfToken();
        if (!csrfToken) {
            return;
        }

        document.querySelectorAll('form[method="post"], form[method="POST"]').forEach((form) => {
            let tokenInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
            if (!tokenInput) {
                tokenInput = document.createElement('input');
                tokenInput.type = 'hidden';
                tokenInput.name = 'csrfmiddlewaretoken';
                form.prepend(tokenInput);
            }
            tokenInput.value = csrfToken;
        });
    };

    // Prevent stale CSRF token issues after login/logout or back navigation.
    syncCsrfTokenForForms();
    document.querySelectorAll('form[method="post"], form[method="POST"]').forEach((form) => {
        form.addEventListener('submit', syncCsrfTokenForForms);
    });

    const navbar = document.querySelector('.premium-navbar');
    const onScroll = () => {
        if (!navbar) {
            return;
        }
        navbar.classList.toggle('is-scrolled', window.scrollY > 16);
    };
    onScroll();
    window.addEventListener('scroll', onScroll);

    const revealTargets = document.querySelectorAll(
        '.course-card, .stat-card, .category-card, .home-panel, .timeline-card, .glass-card, .page-header-shell, .card'
    );
    revealTargets.forEach((item, index) => {
        item.classList.add('reveal-up');
        item.style.setProperty('--reveal-delay', `${Math.min(index * 35, 280)}ms`);
    });

    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });

        revealTargets.forEach((item) => observer.observe(item));
    } else {
        revealTargets.forEach((item) => item.classList.add('is-visible'));
    }

    const autoDismissAlerts = document.querySelectorAll('.alert');
    autoDismissAlerts.forEach((alertEl) => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
            bsAlert.close();
        }, 5000);
    });

    const chatbotShell = document.querySelector('.ai-chatbot-shell');
    if (chatbotShell) {
        const chatbotUrl = chatbotShell.dataset.chatbotUrl;
        const toggleButton = chatbotShell.querySelector('.ai-chatbot-toggle');
        const closeButton = chatbotShell.querySelector('.ai-chatbot-close');
        const navTrigger = document.querySelector('.assistant-nav-trigger');
        const panel = chatbotShell.querySelector('.ai-chatbot-panel');
        const form = chatbotShell.querySelector('.ai-chatbot-form');
        const input = chatbotShell.querySelector('.ai-chatbot-input');
        const voiceButton = chatbotShell.querySelector('.ai-chatbot-voice');
        const messages = chatbotShell.querySelector('.ai-chatbot-messages');
        const suggestions = chatbotShell.querySelector('.ai-chatbot-suggestions');
        let isSending = false;
        let shouldSpeakReply = false;

        const scrollMessagesToBottom = () => {
            messages.scrollTop = messages.scrollHeight;
        };

        const addMessage = (text, type) => {
            const wrapper = document.createElement('div');
            wrapper.className = `ai-chatbot-message ${type === 'user' ? 'is-user' : 'is-bot'}`;

            const bubble = document.createElement('div');
            bubble.className = 'ai-chatbot-bubble';
            bubble.textContent = text;

            wrapper.appendChild(bubble);
            messages.appendChild(wrapper);
            scrollMessagesToBottom();

            if (type === 'bot' && shouldSpeakReply && 'speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = 1;
                utterance.pitch = 1;
                window.speechSynthesis.speak(utterance);
                shouldSpeakReply = false;
            }
        };

        const setSuggestions = (items) => {
            suggestions.innerHTML = '';
            (items || []).slice(0, 4).forEach((item) => {
                const chip = document.createElement('button');
                chip.type = 'button';
                chip.className = 'ai-chatbot-chip';
                chip.textContent = item;
                suggestions.appendChild(chip);
            });
        };

        const addCards = (cards) => {
            if (!cards || !cards.length) {
                return;
            }

            const cardList = document.createElement('div');
            cardList.className = 'ai-chatbot-card-list';

            cards.forEach((card) => {
                const cardLink = document.createElement('a');
                cardLink.className = 'ai-chatbot-card';
                cardLink.href = card.url || '#';

                const title = document.createElement('strong');
                title.textContent = card.title || 'Open';
                cardLink.appendChild(title);

                if (card.meta) {
                    const meta = document.createElement('span');
                    meta.textContent = card.meta;
                    cardLink.appendChild(meta);
                }

                cardList.appendChild(cardLink);
            });

            messages.appendChild(cardList);
            scrollMessagesToBottom();
        };

        const addLinks = (links) => {
            if (!links || !links.length) {
                return;
            }

            const linkRow = document.createElement('div');
            linkRow.className = 'ai-chatbot-link-row';

            links.forEach((item) => {
                const link = document.createElement('a');
                link.className = 'ai-chatbot-inline-link';
                link.href = item.url || '#';
                link.textContent = item.label || 'Open';
                linkRow.appendChild(link);
            });

            messages.appendChild(linkRow);
            scrollMessagesToBottom();
        };

        const toggleChatbot = (shouldOpen) => {
            const open = typeof shouldOpen === 'boolean' ? shouldOpen : panel.hasAttribute('hidden');
            panel.hidden = !open;
            toggleButton.setAttribute('aria-expanded', String(open));
            chatbotShell.classList.toggle('is-open', open);
            if (open) {
                input.focus();
                scrollMessagesToBottom();
            }
        };

        const sendMessage = async (message) => {
            if (!message || isSending) {
                return;
            }

            isSending = true;
            addMessage(message, 'user');
            input.value = '';

            try {
                const response = await fetch(chatbotUrl, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify({ message }),
                });

                let data = {};
                try {
                    data = await response.json();
                } catch (error) {
                    data = {};
                }

                if (!response.ok) {
                    throw new Error(data.reply || 'Chatbot request failed');
                }

                addMessage(data.reply || 'I could not answer that right now.', 'bot');
                addCards(data.cards);
                addLinks(data.links);
                setSuggestions(data.chips);
            } catch (error) {
                addMessage(error.message || 'The assistant is temporarily unavailable. Please try again.', 'bot');
            } finally {
                isSending = false;
            }
        };

        toggleButton.addEventListener('click', () => toggleChatbot());
        closeButton.addEventListener('click', () => toggleChatbot(false));
        if (navTrigger) {
            navTrigger.addEventListener('click', (event) => {
                event.preventDefault();
                toggleChatbot(true);
            });
        }

        form.addEventListener('submit', (event) => {
            event.preventDefault();
            sendMessage(input.value.trim());
        });

        suggestions.addEventListener('click', (event) => {
            const chip = event.target.closest('.ai-chatbot-chip');
            if (!chip) {
                return;
            }
            sendMessage(chip.textContent.trim());
        });

        if (voiceButton) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                voiceButton.disabled = true;
                voiceButton.title = 'Voice input is not supported in this browser.';
            } else {
                const recognition = new SpeechRecognition();
                recognition.lang = 'en-IN';
                recognition.interimResults = false;
                recognition.maxAlternatives = 1;

                recognition.addEventListener('start', () => {
                    voiceButton.classList.add('active');
                });

                recognition.addEventListener('end', () => {
                    voiceButton.classList.remove('active');
                });

                recognition.addEventListener('result', (event) => {
                    const transcript = event.results?.[0]?.[0]?.transcript?.trim();
                    if (!transcript) {
                        return;
                    }
                    input.value = transcript;
                    shouldSpeakReply = true;
                    sendMessage(transcript);
                });

                recognition.addEventListener('error', () => {
                    voiceButton.classList.remove('active');
                    addMessage('Voice input could not start. Please allow microphone access and try again.', 'bot');
                });

                voiceButton.addEventListener('click', () => {
                    shouldSpeakReply = true;
                    toggleChatbot(true);
                    recognition.start();
                });
            }
        }

        if (chatbotShell.dataset.autoOpen === 'student' && !sessionStorage.getItem('assistant_seen')) {
            toggleChatbot(true);
            sessionStorage.setItem('assistant_seen', '1');
        }
    }
});
