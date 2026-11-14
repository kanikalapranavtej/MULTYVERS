(() => {
    const root = document.documentElement;
    const saved = localStorage.getItem('multyvers-theme');

    if (saved) root.dataset.theme = saved;

    const toast = (message) => {
        const el = document.querySelector('#toast');
        if (!el) return;
        el.textContent = message;
        el.classList.add('show');
        setTimeout(() => el.classList.remove('show'), 2800);
    };

    document.addEventListener('click', (event) => {
        const theme = event.target.closest('[data-theme-toggle]');

        if (theme) {
            const next = root.dataset.theme === 'light' ? 'dark' : 'light';
            root.dataset.theme = next;
            localStorage.setItem('multyvers-theme', next);
            toast(`${next === 'light' ? 'Light' : 'Dark'} mode enabled`);
        }

        const menu = event.target.closest('[data-mobile-menu]');
        if (menu) {
            document.querySelector('[data-mobile-nav]')?.classList.toggle('open');
        }

        const filter = event.target.closest('[data-filter-toggle]');
        if (filter) {
            document.querySelector('[data-filter-panel]')?.classList.add('open');
        }

        const close = event.target.closest('[data-filter-close]');
        if (close) {
            document.querySelector('[data-filter-panel]')?.classList.remove('open');
        }

        const side = event.target.closest('.mobile-sidebar-toggle');
        if (side) {
            document.querySelector('.dashboard-sidebar')?.classList.toggle('open');
        }

        const save = event.target.closest('.event-save');

        if (save) {
            event.preventDefault();
            save.classList.toggle('saved');
            toast(save.classList.contains('saved')
                ? 'Event saved to your orbit'
                : 'Event removed from saved');
        }
    });

    const nav = document.querySelector('.site-nav');

    window.addEventListener('scroll', () => {
        if (nav) nav.dataset.scrolled = window.scrollY > 12 ? 'true' : 'false';
    }, { passive: true });

    const counters = document.querySelectorAll('[data-counter]');

    const observer = new IntersectionObserver(entries =>
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('counted');
                observer.unobserve(entry.target);
            }
        }), { threshold: .8 });

    counters.forEach(counter => observer.observe(counter));

    document.querySelectorAll('a[href="#"]').forEach(link =>
        link.addEventListener('click', event => {
            event.preventDefault();
            toast('This area is ready for your Flask route integration.');
        })
    );
})();

// Orbit dock proximity animation
const dock = document.querySelector('[data-orbit-dock]');

if (dock && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const items = [...dock.querySelectorAll('[data-dock-item]')];

    dock.addEventListener('pointermove', event => {
        items.forEach(item => {
            const rect = item.getBoundingClientRect();
            const distance = Math.abs(
                event.clientX - (rect.left + rect.width / 2)
            );

            item.style.transform = distance < 90
                ? `translateY(-${Math.max(0, 4 - distance / 28)}px) scale(${1 + Math.max(0, 0.05 - distance / 180)})`
                : '';
        });
    });

    dock.addEventListener('pointerleave', () =>
        items.forEach(item => item.style.transform = '')
    );
}

// Event registration and cancellation
document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-registration-action]');
    if (!button) return;

    event.preventDefault();
    if (button.disabled) return;

    const action = button.dataset.registrationAction;
    const eventId = button.dataset.eventId;
    if (!eventId || !['register', 'cancel'].includes(action)) return;

    const originalText = button.textContent.trim();
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    button.disabled = true;
    button.textContent = action === 'register' ? 'Registering…' : 'Cancelling…';

    try {
        const response = await fetch(
            action === 'register' ? '/api/registrations/' : `/api/registrations/${eventId}`,
            {
                method: action === 'register' ? 'POST' : 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'Accept': 'application/json'
                },
                ...(action === 'register'
                    ? { body: JSON.stringify({ event_id: Number(eventId) }) }
                    : {})
            }
        );

        const raw = await response.text();
        let data = {};
        try { data = raw ? JSON.parse(raw) : {}; }
        catch { throw new Error('The server returned an unexpected response. Refresh the page and try again.'); }

        if (!response.ok) throw new Error(data.error || 'The request could not be completed.');

        if (action === 'register') {
            button.dataset.registrationAction = 'cancel';
            button.textContent = 'Cancel registration';
            button.classList.add('button-danger');
            const card = button.closest('.registration-card');
            const note = card?.querySelector('[data-registration-feedback]');
            if (note) note.textContent = 'Your place is confirmed. You are registered for this event.';
            toast(data.message || 'Registration confirmed.');
        } else {
            button.dataset.registrationAction = 'register';
            button.textContent = 'Register for event';
            button.classList.remove('button-danger');
            const card = button.closest('.registration-card');
            const note = card?.querySelector('[data-registration-feedback]');
            if (note) note.textContent = 'Your registration has been cancelled.';
            toast(data.message || 'Registration cancelled.');
        }
    } catch (error) {
        toast(error.message || 'Something went wrong. Please try again.');
        button.textContent = originalText;
    } finally {
        button.disabled = false;
    }
});


// Accessible show/hide control for every password field across all portals.
document.querySelectorAll('input[type="password"]').forEach((input) => {
    if (input.dataset.visibilityControl === "ready") return;
    input.dataset.visibilityControl = "ready";
    const wrapper = document.createElement("div");
    wrapper.className = "password-toggle-wrap";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "password-visibility-toggle";
    toggle.setAttribute("aria-label", "Show password");
    toggle.setAttribute("aria-pressed", "false");
    toggle.innerHTML = '<i data-lucide="eye" aria-hidden="true"></i>';
    toggle.addEventListener("click", () => {
        const reveal = input.type === "password";
        input.type = reveal ? "text" : "password";
        toggle.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
        toggle.setAttribute("aria-pressed", String(reveal));
        toggle.innerHTML = reveal
            ? '<i data-lucide="eye-off" aria-hidden="true"></i>'
            : '<i data-lucide="eye" aria-hidden="true"></i>';
        if (window.lucide) window.lucide.createIcons({root: toggle});
    });
    wrapper.appendChild(toggle);
});
