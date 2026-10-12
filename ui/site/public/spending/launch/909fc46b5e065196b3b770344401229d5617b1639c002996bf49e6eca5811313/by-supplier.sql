SELECT authority_id, authority, supplier_id_scheme, supplier_id, supplier,
       COUNT(*) AS award_results, SUM(amount_cents) AS amount_cents
FROM awards
WHERE (:authority = '' OR authority = :authority)
  AND (:supplier = '' OR supplier = :supplier)
  AND decision_date BETWEEN :start AND :end
GROUP BY authority_id, authority, supplier_id_scheme, supplier_id, supplier
ORDER BY amount_cents DESC, authority_id, authority, supplier_id_scheme, supplier_id, supplier;
