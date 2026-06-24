-- ============================================================================
-- SISTEMA DE PRÉSTAMO DE LIBROS PARA BIBLIOTECA ESCOLAR
-- Base de Datos PostgreSQL
-- ============================================================================

-- Limpiar tablas existentes (si existen)
DROP TABLE IF EXISTS prestamos CASCADE;
DROP TABLE IF EXISTS libros CASCADE;
DROP TABLE IF EXISTS autores CASCADE;
DROP TABLE IF EXISTS alumnos CASCADE;
DROP TABLE IF EXISTS multas CASCADE;

-- ============================================================================
-- TABLA: AUTORES
-- Almacena información de los autores de los libros
-- ============================================================================
CREATE TABLE autores (
    id_autor SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    fecha_nacimiento DATE,
    pais VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLA: LIBROS
-- Almacena información de los libros disponibles en la biblioteca
-- ============================================================================
CREATE TABLE libros (
    id_libro SERIAL PRIMARY KEY,
    titulo VARCHAR(150) NOT NULL,
    id_autor INT NOT NULL,
    isbn VARCHAR(20) UNIQUE,
    anio_publicacion INT,
    cantidad_total INT DEFAULT 1,
    cantidad_disponible INT DEFAULT 1,
    estado VARCHAR(20) DEFAULT 'Disponible', -- Disponible, Prestado, Dañado
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_autor) REFERENCES autores(id_autor) ON DELETE CASCADE
);

-- ============================================================================
-- TABLA: ALUMNOS
-- Almacena información de los alumnos que pueden prestar libros
-- ============================================================================
CREATE TABLE alumnos (
    id_alumno SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    grado VARCHAR(20),
    fecha_inscripcion DATE DEFAULT CURRENT_DATE,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLA: PRESTAMOS
-- Registra los préstamos realizados a los alumnos
-- ============================================================================
CREATE TABLE prestamos (
    id_prestamo SERIAL PRIMARY KEY,
    id_alumno INT NOT NULL,
    id_libro INT NOT NULL,
    fecha_prestamo DATE DEFAULT CURRENT_DATE,
    fecha_devolucion_esperada DATE NOT NULL,
    fecha_devolucion_real DATE,
    estado VARCHAR(20) DEFAULT 'Activo', -- Activo, Devuelto, Vencido
    multa_asignada DECIMAL(10, 2) DEFAULT 0.00,
    multa_pagada BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_alumno) REFERENCES alumnos(id_alumno) ON DELETE CASCADE,
    FOREIGN KEY (id_libro) REFERENCES libros(id_libro) ON DELETE CASCADE
);

-- ============================================================================
-- TABLA: MULTAS
-- Registro histórico de multas generadas
-- ============================================================================
CREATE TABLE multas (
    id_multa SERIAL PRIMARY KEY,
    id_prestamo INT NOT NULL,
    id_alumno INT NOT NULL,
    monto DECIMAL(10, 2) NOT NULL,
    motivo VARCHAR(200),
    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pagada BOOLEAN DEFAULT FALSE,
    fecha_pago TIMESTAMP,
    FOREIGN KEY (id_prestamo) REFERENCES prestamos(id_prestamo) ON DELETE CASCADE,
    FOREIGN KEY (id_alumno) REFERENCES alumnos(id_alumno) ON DELETE CASCADE
);

-- ============================================================================
-- FUNCIÓN: CALCULAR_MULTA
-- Calcula la multa por atraso en la devolución ($1.000 por día de atraso)
-- Parámetros: p_id_prestamo INT
-- Retorna: DECIMAL (monto de la multa)
-- ============================================================================
CREATE OR REPLACE FUNCTION calcular_multa(p_id_prestamo INT)
RETURNS DECIMAL AS $$
DECLARE
    v_fecha_esperada DATE;
    v_dias_atraso INT;
    v_multa DECIMAL;
BEGIN
    -- Obtener la fecha de devolución esperada del préstamo
    SELECT fecha_devolucion_esperada INTO v_fecha_esperada
    FROM prestamos
    WHERE id_prestamo = p_id_prestamo;
    
    -- Si el préstamo no existe, retornar 0
    IF v_fecha_esperada IS NULL THEN
        RETURN 0.00;
    END IF;
    
    -- Calcular días de atraso (comparar con hoy)
    v_dias_atraso := EXTRACT(DAY FROM (CURRENT_DATE - v_fecha_esperada))::INT;
    
    -- Si hay atraso, calcular multa ($1.000 por día de atraso)
    IF v_dias_atraso > 0 THEN
        v_multa := v_dias_atraso * 1000.00;
    ELSE
        v_multa := 0.00;
    END IF;
    
    RETURN v_multa;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCIÓN: VERIFICAR_DISPONIBILIDAD_LIBRO
-- Verifica si hay libros disponibles y si se puede prestar
-- Parámetros: p_id_libro INT
-- Retorna: BOOLEAN (TRUE si está disponible)
-- ============================================================================
CREATE OR REPLACE FUNCTION verificar_disponibilidad_libro(p_id_libro INT)
RETURNS BOOLEAN AS $$
DECLARE
    v_cantidad_disponible INT;
BEGIN
    -- Obtener cantidad disponible del libro
    SELECT cantidad_disponible INTO v_cantidad_disponible
    FROM libros
    WHERE id_libro = p_id_libro;
    
    -- Si no existe el libro, retornar FALSE
    IF v_cantidad_disponible IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Retornar TRUE si hay disponibilidad, FALSE en caso contrario
    RETURN v_cantidad_disponible > 0;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCIÓN: VERIFICAR_PUEDE_PRESTAR
-- Verifica si un alumno puede prestar (máximo 3 libros y sin multas pendientes)
-- Parámetros: p_id_alumno INT
-- Retorna: BOOLEAN (TRUE si puede prestar)
-- ============================================================================
CREATE OR REPLACE FUNCTION verificar_puede_prestar(p_id_alumno INT)
RETURNS BOOLEAN AS $$
DECLARE
    v_prestamos_activos INT;
    v_multas_pendientes INT;
BEGIN
    -- Contar préstamos activos del alumno
    SELECT COUNT(*) INTO v_prestamos_activos
    FROM prestamos
    WHERE id_alumno = p_id_alumno AND estado = 'Activo';
    
    -- Contar multas sin pagar del alumno
    SELECT COUNT(*) INTO v_multas_pendientes
    FROM multas
    WHERE id_alumno = p_id_alumno AND pagada = FALSE;
    
    -- Retornar TRUE solo si tiene menos de 3 préstamos activos y sin multas
    RETURN (v_prestamos_activos < 3) AND (v_multas_pendientes = 0);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGER: VERIFICAR_PRÉSTAMO_PERMITIDO
-- Impide el préstamo si el alumno tiene 3 libros o multas sin pagar
-- ============================================================================
CREATE OR REPLACE FUNCTION trig_verificar_prestamo()
RETURNS TRIGGER AS $$
DECLARE
    v_puede_prestar BOOLEAN;
    v_libro_disponible BOOLEAN;
BEGIN
    -- Verificar si el alumno puede prestar
    v_puede_prestar := verificar_puede_prestar(NEW.id_alumno);
    
    -- Verificar si el libro está disponible
    v_libro_disponible := verificar_disponibilidad_libro(NEW.id_libro);
    
    -- Si el alumno no puede prestar, lanzar excepción
    IF NOT v_puede_prestar THEN
        RAISE EXCEPTION 'El alumno no puede prestar más libros. Verifique: máximo 3 libros activos y sin multas pendientes.';
    END IF;
    
    -- Si el libro no está disponible, lanzar excepción
    IF NOT v_libro_disponible THEN
        RAISE EXCEPTION 'El libro no está disponible para préstamo.';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trig_verificar_prestamo_antes_insert
BEFORE INSERT ON prestamos
FOR EACH ROW
EXECUTE FUNCTION trig_verificar_prestamo();

-- ============================================================================
-- TRIGGER: CAMBIAR_ESTADO_LIBRO
-- Cambia automáticamente el estado del libro a 'Prestado' al crear un préstamo
-- ============================================================================
CREATE OR REPLACE FUNCTION trig_cambiar_estado_libro()
RETURNS TRIGGER AS $$
BEGIN
    -- Actualizar cantidad disponible y estado del libro
    UPDATE libros
    SET cantidad_disponible = cantidad_disponible - 1,
        estado = CASE 
                    WHEN cantidad_disponible - 1 = 0 THEN 'Prestado'
                    ELSE 'Disponible'
                 END
    WHERE id_libro = NEW.id_libro;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trig_cambiar_estado_libro_despues_insert
AFTER INSERT ON prestamos
FOR EACH ROW
EXECUTE FUNCTION trig_cambiar_estado_libro();

-- ============================================================================
-- PROCEDIMIENTO: REALIZAR_DEVOLUCION
-- Realiza la devolución de un libro y asigna multa si es necesario
-- Parámetros: p_id_prestamo INT
-- ============================================================================
CREATE OR REPLACE PROCEDURE realizar_devolucion(p_id_prestamo INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id_alumno INT;
    v_id_libro INT;
    v_multa_calculada DECIMAL;
    v_dias_atraso INT;
BEGIN
    -- Obtener información del préstamo
    SELECT id_alumno, id_libro, EXTRACT(DAY FROM (CURRENT_DATE - fecha_devolucion_esperada))::INT
    INTO v_id_alumno, v_id_libro, v_dias_atraso
    FROM prestamos
    WHERE id_prestamo = p_id_prestamo AND estado = 'Activo';
    
    -- Verificar si el préstamo existe y está activo
    IF v_id_alumno IS NULL THEN
        RAISE EXCEPTION 'El préstamo no existe o ya fue devuelto.';
    END IF;
    
    -- Calcular multa si hay atraso
    v_multa_calculada := calcular_multa(p_id_prestamo);
    
    -- Actualizar el préstamo
    UPDATE prestamos
    SET fecha_devolucion_real = CURRENT_DATE,
        estado = 'Devuelto',
        multa_asignada = v_multa_calculada,
        multa_pagada = FALSE
    WHERE id_prestamo = p_id_prestamo;
    
    -- Incrementar cantidad disponible del libro
    UPDATE libros
    SET cantidad_disponible = cantidad_disponible + 1,
        estado = 'Disponible'
    WHERE id_libro = v_id_libro;
    
    -- Si hay multa, registrarla en la tabla de multas
    IF v_multa_calculada > 0 THEN
        INSERT INTO multas (id_prestamo, id_alumno, monto, motivo, pagada)
        VALUES (p_id_prestamo, v_id_alumno, v_multa_calculada, 
                'Atraso en devolución: ' || v_dias_atraso || ' días', FALSE);
    END IF;
    
    -- Mensaje de confirmación
    RAISE NOTICE 'Devolución realizada exitosamente. Multa asignada: $%.2f', v_multa_calculada;
END;
$$;

-- ============================================================================
-- PROCEDIMIENTO: PAGAR_MULTA
-- Registra el pago de una multa pendiente
-- Parámetros: p_id_multa INT
-- ============================================================================
CREATE OR REPLACE PROCEDURE pagar_multa(p_id_multa INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id_prestamo INT;
    v_monto DECIMAL;
BEGIN
    -- Obtener información de la multa
    SELECT id_prestamo, monto INTO v_id_prestamo, v_monto
    FROM multas
    WHERE id_multa = p_id_multa AND pagada = FALSE;
    
    -- Verificar si la multa existe y no está pagada
    IF v_id_prestamo IS NULL THEN
        RAISE EXCEPTION 'La multa no existe o ya fue pagada.';
    END IF;
    
    -- Actualizar el estado de la multa
    UPDATE multas
    SET pagada = TRUE,
        fecha_pago = CURRENT_TIMESTAMP
    WHERE id_multa = p_id_multa;
    
    -- Actualizar el préstamo indicando que la multa fue pagada
    UPDATE prestamos
    SET multa_pagada = TRUE
    WHERE id_prestamo = v_id_prestamo;
    
    -- Mensaje de confirmación
    RAISE NOTICE 'Multa pagada exitosamente. Monto: $%.2f', v_monto;
END;
$$;

-- ============================================================================
-- INSERTS DE PRUEBA: AUTORES
-- ============================================================================
INSERT INTO autores (nombre, apellido, fecha_nacimiento, pais) VALUES
('Gabriel', 'García Márquez', '1927-03-06', 'Colombia'),
('Jorge Luis', 'Borges', '1899-08-24', 'Argentina'),
('Isabel', 'Allende', '1942-08-02', 'Chile'),
('Carlos', 'Ruiz Zafón', '1964-09-25', 'España'),
('Paulo', 'Coelho', '1947-08-24', 'Brasil');

-- ============================================================================
-- INSERTS DE PRUEBA: LIBROS
-- ============================================================================
INSERT INTO libros (titulo, id_autor, isbn, anio_publicacion, cantidad_total, cantidad_disponible, estado) VALUES
('Cien años de soledad', 1, '978-8437604947', 1967, 5, 5, 'Disponible'),
('El laberinto de la soledad', 2, '978-8466338898', 1962, 3, 3, 'Disponible'),
('La casa de los espíritus', 3, '978-8401428840', 1982, 4, 4, 'Disponible'),
('La sombra del viento', 4, '978-8408076490', 2001, 6, 6, 'Disponible'),
('El Alquimista', 5, '978-8408050895', 1988, 5, 5, 'Disponible'),
('Ficciones', 2, '978-8466351225', 1944, 2, 2, 'Disponible'),
('Amor en los tiempos del cólera', 1, '978-8437602547', 1985, 3, 3, 'Disponible'),
('Paula', 3, '978-8401419732', 1994, 2, 2, 'Disponible');

-- ============================================================================
-- INSERTS DE PRUEBA: ALUMNOS
-- ============================================================================
INSERT INTO alumnos (nombre, apellido, email, grado, fecha_inscripcion, activo) VALUES
('Juan', 'Pérez García', 'juan.perez@escuela.edu', '10A', '2024-01-15', TRUE),
('María', 'López Rodríguez', 'maria.lopez@escuela.edu', '11B', '2024-01-16', TRUE),
('Carlos', 'Martínez González', 'carlos.martinez@escuela.edu', '10C', '2024-01-17', TRUE),
('Ana', 'García Fernández', 'ana.garcia@escuela.edu', '11A', '2024-01-18', TRUE),
('Luis', 'Rodríguez Santos', 'luis.rodriguez@escuela.edu', '10B', '2024-01-19', TRUE),
('Sofía', 'Hernández López', 'sofia.hernandez@escuela.edu', '11C', '2024-01-20', TRUE),
('Diego', 'Sánchez Ruiz', 'diego.sanchez@escuela.edu', '10A', '2024-01-21', TRUE),
('Laura', 'Flores Díaz', 'laura.flores@escuela.edu', '11B', '2024-01-22', TRUE);

-- ============================================================================
-- INSERTS DE PRUEBA: PRÉSTAMOS (para demostración)
-- ============================================================================
INSERT INTO prestamos (id_alumno, id_libro, fecha_prestamo, fecha_devolucion_esperada, estado) VALUES
(1, 1, CURRENT_DATE - INTERVAL '7 days', CURRENT_DATE + 7, 'Activo'),
(2, 2, CURRENT_DATE - INTERVAL '5 days', CURRENT_DATE + 9, 'Activo'),
(3, 3, CURRENT_DATE - INTERVAL '3 days', CURRENT_DATE + 11, 'Activo');

-- ============================================================================
-- CONFIRMACIÓN DE CREACIÓN
-- ============================================================================
-- Los triggers y funciones están listos para ser utilizados por la aplicación
-- La base de datos está completamente configurada y funcional

