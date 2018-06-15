-- Exports submissions and primary category from classic db.
-- For use with process_submissions.py
-- 
-- mysql -u root -B arXiv < export_submissions.sql > submissions.tsv
SELECT sub.*, cat.category
FROM arXiv.arXiv_submissions sub, arXiv.arXiv_submission_category cat 
WHERE sub.submission_id = cat.submission_id AND cat.is_primary = 1
LIMIT 1000;
