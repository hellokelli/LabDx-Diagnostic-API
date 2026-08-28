SELECT DISTINCT
    d.subject_id, d.icd_code
FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
LEFT JOIN `physionet-data.mimiciv_3_1_hosp.d_icd_diagnoses` diag
    ON d.icd_code = diag.icd_code 
    AND d.icd_version = diag.icd_version
WHERE d.icd_code IN ('570', '5700','D570','D571','D572','572','28260','571')
