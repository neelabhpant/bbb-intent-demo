-- Portable feature source.
--
-- Selects and cleans the raw session columns from the `sessions` table into the
-- canonical model-input contract. ANSI-plain so it runs unchanged on DuckDB (local)
-- and Impala (Cloudera). No engine-specific syntax: no SELECT * EXCLUDE, no QUALIFY,
-- no list types, no window functions.
--
-- Row-level feature derivation and all encoding live in src/core/features.py, which is
-- shared by training and serving to guarantee no train/serve skew. This query stays a
-- clean, portable projection: explicit column selection, null handling, and stable
-- numeric typing. Keeping derivations out of SQL is deliberate, since a single serve
-- payload never touches the warehouse.
--
-- Porting note: Impala folds unquoted identifiers to lower case. When the Iceberg table
-- is created with these mixed-case column names, the result columns may come back lower
-- case; reconcile that at the data-access edge (see PORTING.md), not by editing logic.
SELECT
    CAST(COALESCE(Administrative, 0) AS BIGINT)           AS Administrative,
    CAST(COALESCE(Administrative_Duration, 0) AS DOUBLE)  AS Administrative_Duration,
    CAST(COALESCE(Informational, 0) AS BIGINT)            AS Informational,
    CAST(COALESCE(Informational_Duration, 0) AS DOUBLE)   AS Informational_Duration,
    CAST(COALESCE(ProductRelated, 0) AS BIGINT)           AS ProductRelated,
    CAST(COALESCE(ProductRelated_Duration, 0) AS DOUBLE)  AS ProductRelated_Duration,
    CAST(COALESCE(BounceRates, 0) AS DOUBLE)              AS BounceRates,
    CAST(COALESCE(ExitRates, 0) AS DOUBLE)                AS ExitRates,
    CAST(COALESCE(PageValues, 0) AS DOUBLE)               AS PageValues,
    CAST(COALESCE(SpecialDay, 0) AS DOUBLE)               AS SpecialDay,
    Month                                                 AS Month,
    CAST(COALESCE(OperatingSystems, 0) AS BIGINT)         AS OperatingSystems,
    CAST(COALESCE(Browser, 0) AS BIGINT)                  AS Browser,
    CAST(COALESCE(Region, 0) AS BIGINT)                   AS Region,
    CAST(COALESCE(TrafficType, 0) AS BIGINT)              AS TrafficType,
    VisitorType                                           AS VisitorType,
    Weekend                                               AS Weekend,
    Revenue                                               AS Revenue
FROM sessions;
