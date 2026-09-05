SELECT award_key, authority_id, authority, supplier_id_scheme, supplier_id,
       supplier, contract_id, lot_id, decision_date, amount_cents,
       source_url, entry_sha256, capture_path
FROM awards
WHERE (:authority = '' OR authority = :authority)
  AND (:supplier = '' OR supplier = :supplier)
  AND decision_date BETWEEN :start AND :end
ORDER BY decision_date, source_record_id, money_fact_id;
