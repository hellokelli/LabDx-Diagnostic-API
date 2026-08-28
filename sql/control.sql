WITH healthy_dates AS (
    SELECT 
        l.subject_id,
        l.charttime AS healthy_date
    FROM `physionet-data.mimiciv_3_1_hosp.labevents` l
    WHERE l.itemid IN (51221, 51222, 51250, 51277, 51279)
    AND l.valuenum IS NOT NULL
    AND l.valuenum > 0
    GROUP BY l.subject_id, l.charttime
    HAVING 
        COUNT(DISTINCT l.itemid) = 5
        AND MAX(CASE WHEN l.itemid = 51222 THEN IF(l.valuenum BETWEEN 12.0 AND 16.0, 1, 0) END) = 1
        AND MAX(CASE WHEN l.itemid = 51221 THEN IF(l.valuenum BETWEEN 36 AND 46, 1, 0) END) = 1
        AND MAX(CASE WHEN l.itemid = 51250 THEN IF(l.valuenum BETWEEN 80 AND 100, 1, 0) END) = 1
        AND MAX(CASE WHEN l.itemid = 51277 THEN IF(l.valuenum BETWEEN 11.5 AND 14.5, 1, 0) END) = 1
        AND MAX(CASE WHEN l.itemid = 51279 THEN IF(l.valuenum BETWEEN 4.2 AND 6.1, 1, 0) END) = 1
        AND l.subject_id NOT IN (
            SELECT DISTINCT subject_id
            FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd`
            WHERE icd_code LIKE '57%' 
               OR icd_code LIKE '56%'
               OR icd_code LIKE '282%'
               OR icd_code LIKE '582%'
        )
)
SELECT 
    l.subject_id,
    l.charttime,
    li.label,
    l.valuenum,
    l.valueuom,
    l.ref_range_lower,
    l.ref_range_upper,
    l.flag
FROM `physionet-data.mimiciv_3_1_hosp.labevents` l
LEFT JOIN `physionet-data.mimiciv_3_1_hosp.d_labitems` li
    ON l.itemid = li.itemid
WHERE EXISTS (
    SELECT 1
    FROM healthy_dates hd
    WHERE hd.subject_id = l.subject_id
    AND l.charttime = hd.healthy_date
)
AND l.itemid IN (
    51221, 51222, 51248, 51249, 51250, 51265, 51279, 51277, 52159, 51301
)
AND l.valuenum IS NOT NULL
AND l.valuenum > 0
ORDER BY l.subject_id, l.charttime