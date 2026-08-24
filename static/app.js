/* =========================================
   FIREBASE AUTHENTICATION
   Any Firebase Email/Password user can login
   ========================================= */

function unlockApp() {
    const login = $('#loginScreen');
    const app = $('#appShell');

    if (login) login.hidden = true;
    if (app) app.hidden = false;
}

function lockApp() {
    const login = $('#loginScreen');
    const app = $('#appShell');

    if (app) app.hidden = true;
    if (login) login.hidden = false;
}

async function logout() {
    try {
        await firebase.auth().signOut();
    } catch (error) {
        console.error('Logout failed:', error);
        toast('Logout failed');
    }
}

function initLogin() {

    const form = $('#loginForm');
    const errorBox = $('#loginError');
    const toggle = $('#togglePassword');
    const password = $('#loginPassword');

    if (!form || !errorBox || !password) {
        console.error('Login elements not found.');
        return;
    }

    if (typeof firebase === 'undefined' || !firebase.auth) {
        console.error('Firebase Authentication is not loaded.');
        errorBox.textContent =
            'Firebase Authentication is not loaded.';
        errorBox.style.display = 'block';
        return;
    }

    /* Firebase controls the login session */
    firebase.auth().onAuthStateChanged(function(user) {

        if (user) {
            unlockApp();
        } else {
            lockApp();
        }

    });

    /* LOGIN */
    form.addEventListener('submit', async function(event) {

        event.preventDefault();

        const email =
            $('#loginUsername').value.trim().toLowerCase();

        const pass = password.value;

        errorBox.style.display = 'none';
        errorBox.textContent = '';

        if (!email || !pass) {
            errorBox.textContent =
                'Please enter email and password.';
            errorBox.style.display = 'block';
            return;
        }

        try {

            await firebase.auth()
                .signInWithEmailAndPassword(email, pass);

            password.value = '';

        } catch (error) {

            console.error('Firebase login error:', error);

            errorBox.textContent =
                'Invalid email or password.';

            errorBox.style.display = 'block';

            password.value = '';
            password.focus();
        }

    });

    /* SHOW / HIDE PASSWORD */
    toggle?.addEventListener('click', function() {

        if (password.type === 'password') {
            password.type = 'text';
            toggle.textContent = 'Hide';
        } else {
            password.type = 'password';
            toggle.textContent = 'Show';
        }

    });
}

initLogin();
