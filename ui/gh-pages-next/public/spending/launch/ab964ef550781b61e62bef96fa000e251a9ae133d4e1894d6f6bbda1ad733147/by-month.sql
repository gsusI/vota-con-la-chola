SELECT substr(decision_date, 1, 7) AS month,
       COUNT(*) AS award_results, SUM(amount_cents) AS amount_cents
FROM awards
WHERE (:authority = '' OR authority = :authority)
  AND (:supplier = '' OR supplier = :supplier)
  AND decision_date BETWEEN :start AND :end
GROUP BY month ORDER BY month;
