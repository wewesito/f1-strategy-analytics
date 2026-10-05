-- 1. Ganador de cada carrera
SELECT Round, Event, Abbreviation AS ganador, TeamName AS equipo
FROM results
WHERE Position = 1
ORDER BY Round;

-- 2. Puntos y podios por piloto (solo carreras, sin sprints)
SELECT Abbreviation AS piloto,
       SUM(Points) AS puntos,
       COUNT(*) FILTER (WHERE Position <= 3) AS podios,
       COUNT(*) FILTER (WHERE Position = 1) AS victorias
FROM results
GROUP BY Abbreviation
ORDER BY puntos DESC;

-- 3. Vuelta limpia más rápida de cada carrera
SELECT Round, Event,
       arg_min(Driver, LapTimeSec) AS piloto,
       ROUND(MIN(LapTimeSec), 3) AS mejor_vuelta_s
FROM laps
GROUP BY Round, Event
ORDER BY Round;

-- 4. Número medio de paradas por carrera
SELECT Event, ROUND(AVG(paradas), 2) AS paradas_medias
FROM (
    SELECT Event, Driver, MAX(Stint) - 1 AS paradas
    FROM laps
    GROUP BY Event, Driver
)
GROUP BY Event
ORDER BY paradas_medias DESC;

-- 5. Ritmo medio por equipo en toda la temporada
SELECT Team AS equipo,
       ROUND(AVG(LapTimeSec), 3) AS ritmo_medio_s,
       COUNT(*) AS vueltas
FROM laps
GROUP BY Team
ORDER BY ritmo_medio_s;

-- 6. Ritmo por equipo (justo): distancia media en % al más rápido de cada carrera
WITH ritmo AS (
    SELECT Round, Team, MEDIAN(LapTimeSec) AS ritmo_equipo
    FROM laps
    GROUP BY Round, Team
),
gaps AS (
    SELECT Team,
           (ritmo_equipo / MIN(ritmo_equipo) OVER (PARTITION BY Round) - 1) * 100 AS gap_pct
    FROM ritmo
)
SELECT Team AS equipo,
       ROUND(AVG(gap_pct), 2) AS gap_medio_pct,
       COUNT(*) AS carreras
FROM gaps
GROUP BY Team
ORDER BY gap_medio_pct;