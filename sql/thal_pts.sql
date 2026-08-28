SELECT DISTINCT
    d.subject_id
FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
WHERE d.icd_code IN ('D56.3', '28246', 'D563', '563');