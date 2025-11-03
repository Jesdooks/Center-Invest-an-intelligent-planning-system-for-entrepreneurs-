// Простая версия авторизации без модулей
console.log('🔧 Скрипт auth-simple.js загружен');

function initAuthSimple() {
    console.log('🔧 Простая инициализация авторизации...');
    
    // Ждем загрузки DOM
    if (document.readyState === 'loading') {
        console.log('🔧 DOM еще загружается, ждем...');
        document.addEventListener('DOMContentLoaded', initAuthComponents);
    } else {
        console.log('🔧 DOM уже загружен, запускаем сразу');
        initAuthComponents();
    }
}

// Инициализируем после загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuthSimple);
} else {
    initAuthSimple();
}

function initAuthComponents() {
    console.log('🔧 Инициализация компонентов авторизации...');
    console.log('🔧 document.readyState:', document.readyState);
    console.log('🔧 document.body:', document.body);
    
    const API_BASE_URL = window.location.origin;
    let currentUser = null;

    // Элементы интерфейса
    const authButtons = document.querySelector('.auth-buttons');
    const userInfo = document.getElementById('userInfo');
    const userName = document.getElementById('userName');
    
    console.log('🔧 Поиск элементов...');
    console.log('🔧 authButtons:', authButtons);
    console.log('🔧 userInfo:', userInfo);
    console.log('🔧 userName:', userName);
    
    console.log('🔧 Найденные элементы:', {
        authButtons: authButtons,
        userInfo: userInfo,
        userName: userName
    });
    
    // Убеждаемся что начальное состояние правильное
    if (authButtons) {
        console.log('🔧 Найден блок authButtons');
    } else {
        console.error('❌ Блок authButtons не найден!');
    }
    if (userInfo) {
        console.log('🔧 Найден блок userInfo');
    } else {
        console.error('❌ Блок userInfo не найден!');
    }
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

    console.log('🔧 Элементы найдены:', {
        registerSubmit: !!registerSubmit,
        loginSubmit: !!loginSubmit,
        logoutBtn: !!logoutBtn
    });

    // Проверяем, есть ли сохраненный пользователь
    function checkStoredUser() {
        const storedUser = localStorage.getItem('currentUser');
        console.log('🔧 Сохраненный пользователь:', storedUser);
        if (storedUser) {
            currentUser = JSON.parse(storedUser);
            console.log('🔧 Парсированный пользователь:', currentUser);
            showUserInfo();
        } else {
            console.log('🔧 Пользователь не найден, показываем кнопки авторизации');
            hideUserInfo();
        }
    }

    // Показываем информацию о пользователе
    function showUserInfo() {
        if (currentUser) {
            // Скрываем кнопки авторизации
            if (authButtons) authButtons.classList.add('d-none');
            
            // Показываем информацию о пользователе
            if (userInfo) userInfo.classList.remove('d-none');
            if (userName) userName.textContent = `${currentUser.first_name} ${currentUser.last_name}`;
            
            console.log('✅ Пользователь вошел в систему:', currentUser);
        } else {
            // Если пользователя нет, показываем кнопки
            hideUserInfo();
        }
    }

    // Скрываем информацию о пользователе
    function hideUserInfo() {
        // Показываем кнопки авторизации
        if (authButtons) authButtons.classList.remove('d-none');
        // Скрываем информацию о пользователе
        if (userInfo) userInfo.classList.add('d-none');
        currentUser = null;
        localStorage.removeItem('currentUser');
        console.log('🔧 Кнопки авторизации показаны');
    }

    // Очистка форм
    function clearForms() {
        if (loginForm) loginForm.reset();
        if (registerForm) registerForm.reset();
        if (loginError) loginError.classList.add('d-none');
        if (registerError) registerError.classList.add('d-none');
        if (registerSuccess) registerSuccess.classList.add('d-none');
    }

    // Показ ошибки
    function showError(errorElement, message) {
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
        }
    }

    // Скрытие ошибки
    function hideError(errorElement) {
        if (errorElement) {
            errorElement.classList.add('d-none');
        }
    }

    // Валидация номера телефона
    function validatePhone(phone) {
        // Убираем все пробелы, дефисы и скобки
        const cleanPhone = phone.replace(/[\s\-\(\)]/g, '');
        
        // Проверяем различные форматы российских номеров
        const patterns = [
            /^\+7[0-9]{10}$/,           // +79188989743
            /^8[0-9]{10}$/,             // 89188989743
            /^7[0-9]{10}$/,             // 79188989743
            /^\+7\s?\(?[0-9]{3}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$/, // +7 (918) 898-97-43
            /^8\s?\(?[0-9]{3}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$/,   // 8 (918) 898-97-43
        ];
        
        return patterns.some(pattern => pattern.test(cleanPhone));
    }

    // Валидация пароля
    function validatePassword(password) {
        return password.length >= 6;
    }

    // Обработка входа
    async function handleLogin() {
        console.log('🔧 Обработка входа...');
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
                if (loginModal) loginModal.hide();
                
                console.log('✅ Успешный вход:', data);
            } else {
                showError(loginError, data.detail || 'Ошибка входа');
            }
        } catch (error) {
            console.error('❌ Ошибка входа:', error);
            showError(loginError, 'Ошибка соединения с сервером');
        }
    }

    // Обработка регистрации
    async function handleRegister() {
        console.log('🔧 Обработка регистрации...');
        const firstName = document.getElementById('registerFirstName').value.trim();
        const lastName = document.getElementById('registerLastName').value.trim();
        const phone = document.getElementById('registerPhone').value.trim();
        const password = document.getElementById('registerPassword').value;
        const passwordConfirm = document.getElementById('registerPasswordConfirm').value;
        
        console.log('🔧 Данные формы:', { firstName, lastName, phone, password: '***', passwordConfirm: '***' });

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
            console.log('🔧 Отправляем запрос на регистрацию...');
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
            console.log('🔧 Ответ сервера:', data);

            if (response.ok) {
                hideError(registerError);
                
                // После успешной регистрации сразу входим в систему
                currentUser = {
                    user_id: data.user_id,
                    first_name: data.first_name,
                    last_name: data.last_name,
                    phone_number: phone
                };
                
                // Сохраняем пользователя в localStorage
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                
                // Показываем информацию о пользователе
                showUserInfo();
                
                // Очищаем форму
                if (registerForm) registerForm.reset();
                
                // Закрываем модальное окно
                const registerModal = bootstrap.Modal.getInstance(document.getElementById('registerModal'));
                if (registerModal) registerModal.hide();
                
                // Показываем сообщение об успехе
                if (registerSuccess) {
                    registerSuccess.textContent = 'Регистрация успешна! Добро пожаловать в систему!';
                    registerSuccess.classList.remove('d-none');
                }
                
                console.log('✅ Успешная регистрация и вход:', data);
            } else {
                showError(registerError, data.detail || 'Ошибка регистрации');
            }
        } catch (error) {
            console.error('❌ Ошибка регистрации:', error);
            showError(registerError, 'Ошибка соединения с сервером');
        }
    }

    // Обработка выхода
    function handleLogout() {
        hideUserInfo();
        console.log('Пользователь вышел из системы');
    }

    // Обработчики событий
    if (registerSubmit) {
        registerSubmit.addEventListener('click', handleRegister);
        console.log('✅ Обработчик регистрации добавлен');
    } else {
        console.error('❌ Элемент registerSubmit не найден!');
    }
    
    if (loginSubmit) {
        loginSubmit.addEventListener('click', handleLogin);
        console.log('✅ Обработчик входа добавлен');
    } else {
        console.error('❌ Элемент loginSubmit не найден!');
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
        console.log('✅ Обработчик выхода добавлен');
    } else {
        console.error('❌ Элемент logoutBtn не найден!');
    }

    // Очистка ошибок при изменении полей
    if (loginForm) {
        loginForm.addEventListener('input', () => hideError(loginError));
    }
    if (registerForm) {
        registerForm.addEventListener('input', () => {
            hideError(registerError);
            hideError(registerSuccess);
        });
    }

    // Очистка форм при закрытии модальных окон
    const loginModal = document.getElementById('loginModal');
    const registerModal = document.getElementById('registerModal');
    
    if (loginModal) {
        loginModal.addEventListener('hidden.bs.modal', clearForms);
    }
    if (registerModal) {
        registerModal.addEventListener('hidden.bs.modal', clearForms);
    }

    // Инициализация
    checkStoredUser();
}
