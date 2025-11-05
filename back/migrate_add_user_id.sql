-- Миграция для добавления связи между таблицами users и addresses
-- Выполните этот скрипт в вашей базе данных PostgreSQL

-- 1. Добавляем колонку user_id, если её нет
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'addresses' AND column_name = 'user_id'
    ) THEN
        -- Добавляем колонку user_id с дефолтным значением 1
        ALTER TABLE addresses ADD COLUMN user_id INTEGER DEFAULT 1 NOT NULL;
        
        -- Создаем индекс для быстрого поиска
        CREATE INDEX IF NOT EXISTS idx_addresses_user_id ON addresses(user_id);
        
        -- Добавляем внешний ключ с CASCADE удалением
        ALTER TABLE addresses 
        ADD CONSTRAINT fk_addresses_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES users(user_id) 
        ON DELETE CASCADE;
        
        RAISE NOTICE 'Колонка user_id добавлена успешно';
    ELSE
        RAISE NOTICE 'Колонка user_id уже существует';
    END IF;
END $$;

-- 2. Проверяем, что внешний ключ создан правильно
SELECT 
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conrelid = 'addresses'::regclass
AND conname = 'fk_addresses_user_id';

