-- EvoFlow aborts production startup when TypeORM reports pending migrations.
-- The runtime needs read-only migration metadata for that guard, never mutation access.
grant select on table hablas_evoflow_production.migrations to hablas_evo_prod_flow;
revoke insert, update, delete, truncate on table hablas_evoflow_production.migrations from hablas_evo_prod_flow;
