// Компонент для обработки авторизации
export default function initAuth() {
    const API_BASE_URL = window.location.origin;
    let currentUser = null;

    // Элементы интерфейса
    const authButtons = document.querySelector('.auth-buttons');
    const userInfo = document.getElementById('userInfo');
    const userName = document.getElementById('userName');
    const logoutBtn = document.getElementById('logoutBtn');

    // Элементы форм
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const loginSubmit = document.getElementById('loginSubmit');
    const registerSubmit = document.getElementById('registerSubmit');

    // Элементы ошибок
    const loginError = document.getElementById('loginError');
    const registerError = document.getElementById('registerError');
    const registerSuccess = document.getElementById('registerSuccess');

    // Проверяем, есть ли сохраненный пользователь
    function checkStoredUser() {
        const storedUser = localStorage.getItem('currentUser');
        if (storedUser) {
            currentUser = JSON.parse(storedUser);
            showUserInfo();
        }
    }

    // Показываем информацию о пользователе
    function showUserInfo() {
        if (currentUser) {
            authButtons.classList.add('d-none');
            userInfo.classList.remove('d-none');
            userName.textContent = `${currentUser.first_name} ${currentUser.last_name}`;
        }
    }

    // Скрываем информацию о пользователе
    function hideUserInfo() {
        authButtons.classList.remove('d-none');
        userInfo.classList.add('d-none');
        currentUser = null;
        localStorage.removeItem('currentUser');
    }

    // Очистка форм
    function clearForms() {
        loginForm.reset();
        registerForm.reset();
        loginError.classList.add('d-none');
        registerError.classList.add('d-none');
        registerSuccess.classList.add('d-none');
    }

    // Показ ошибки
    function showError(errorElement, message) {
        errorElement.textContent = message;
        errorElement.classList.remove('d-none');
    }

    // Скрытие ошибки
    function hideError(errorElement) {
        errorElement.classList.add('d-none');
    }

    // Валидация номера телефона
    function validatePhone(phone) {
        const phoneRegex = /^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$/;
        return phoneRegex.test(phone.replace(/\s/g, ''));
    }

    // Валидация пароля
    function validatePassword(password) {
        return password.length >= 6;
    }

    // Обработка входа
    async function handleLogin() {
        const phone = document.getElementById('loginPhone').value.trim();
        const password = document.getElementById('loginPassword').value;

        // Валидация
        if (!phone || !password) {
            showError(loginError, 'Заполните все поля');
            return;
        }

        if (!validatePhone(phone)) {
            showError(loginError, 'Введите корректный номер телефона');
            return;
        }

        if (!validatePassword(password)) {
            showError(loginError, 'Пароль должен содержать минимум 6 символов');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    phone_number: phone,
                    password: password
                })
            });

            const data = await response.json();

            if (response.ok) {
                currentUser = data;
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                showUserInfo();
                clearForms();
                
                // Закрываем модальное окно
                const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
                loginModal.hide();
                
                console.log('Успешный вход:', data);
            } else {
                showError(loginError, data.detail || 'Ошибка входа');
            }
        } catch (error) {
            console.error('Ошибка входа:', error);
            showError(loginError, 'Ошибка соединения с сервером');
        }
    }

    // Обработка регистрации
    async function handleRegister() {
        const firstName = document.getElementById('registerFirstName').value.trim();
        const lastName = document.getElementById('registerLastName').value.trim();
        const phone = document.getElementById('registerPhone').value.trim();
        const password = document.getElementById('registerPassword').value;
        const passwordConfirm = document.getElementById('registerPasswordConfirm').value;

        // Валидация
        if (!firstName || !lastName || !phone || !password || !passwordConfirm) {
            showError(registerError, 'Заполните все поля');
            return;
        }

        if (!validatePhone(phone)) {
            showError(registerError, 'Введите корректный номер телефона');
            return;
        }

        if (!validatePassword(password)) {
            showError(registerError, 'Пароль должен содержать минимум 6 символов');
            return;
        }

        if (password !== passwordConfirm) {
            showError(registerError, 'Пароли не совпадают');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    phone_number: phone,
                    password: password
                })
            });

            const data = await response.json();

            if (response.ok) {
                hideError(registerError);
                registerSuccess.textContent = 'Регистрация успешна! Теперь вы можете войти в систему.';
                registerSuccess.classList.remove('d-none');
                
                // Очищаем форму
                registerForm.reset();
                
                console.log('Успешная регистрация:', data);
            } else {
                showError(registerError, data.detail || 'Ошибка регистрации');
            }
        } catch (error) {
            console.error('Ошибка регистрации:', error);
            showError(registerError, 'Ошибка соединения с сервером');
        }
    }

    // Обработка выхода
    function handleLogout() {
        hideUserInfo();
        console.log('Пользователь вышел из системы');
    }

    // Обработчики событий
    loginSubmit.addEventListener('click', handleLogin);
    registerSubmit.addEventListener('click', handleRegister);
    logoutBtn.addEventListener('click', handleLogout);

    // Очистка ошибок при изменении полей
    loginForm.addEventListener('input', () => hideError(loginError));
    registerForm.addEventListener('input', () => {
        hideError(registerError);
        hideError(registerSuccess);
    });

    // Очистка форм при закрытии модальных окон
    document.getElementById('loginModal').addEventListener('hidden.bs.modal', clearForms);
    document.getElementById('registerModal').addEventListener('hidden.bs.modal', clearForms);

    // Инициализация
    checkStoredUser();

    // Экспортируем функции для использования в других модулях
    return {
        getCurrentUser: () => currentUser,
        isLoggedIn: () => !!currentUser,
        logout: handleLogout
    };
}
