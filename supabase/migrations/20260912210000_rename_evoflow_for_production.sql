begin;

do $$
begin
  if exists (select 1 from pg_namespace where nspname = 'hablas_evoflow_production') then
    raise exception 'hablas_evoflow_production already exists';
  end if;
  if not exists (select 1 from pg_namespace where nspname = 'hablas_evoflow_staging') then
    raise exception 'hablas_evoflow_staging is missing';
  end if;
  execute 'alter schema hablas_evoflow_staging rename to hablas_evoflow_production';
end $$;

grant usage on schema public to hablas_evo_prod_main, hablas_evo_prod_main_migrator;
grant create on schema public to hablas_evo_prod_main_migrator;
grant usage on schema hablas_evoflow_production to hablas_evo_prod_flow, hablas_evo_prod_flow_migrator;
grant create on schema hablas_evoflow_production to hablas_evo_prod_flow_migrator;

grant hablas_evo_stg_main_migrator to postgres;
set local role hablas_evo_stg_main_migrator;
grant select, insert, update, delete on all tables in schema public to hablas_evo_prod_main, hablas_evo_prod_main_migrator;
grant usage, select on all sequences in schema public to hablas_evo_prod_main, hablas_evo_prod_main_migrator;
reset role;

grant hablas_evo_stg_flow_migrator to postgres;
set local role hablas_evo_stg_flow_migrator;
grant select, insert, update, delete on all tables in schema hablas_evoflow_production to hablas_evo_prod_flow, hablas_evo_prod_flow_migrator;
grant usage, select on all sequences in schema hablas_evoflow_production to hablas_evo_prod_flow, hablas_evo_prod_flow_migrator;
revoke all on table hablas_evoflow_production.migrations from hablas_evo_prod_flow;
grant select, insert, update, delete on table hablas_evoflow_production.migrations to hablas_evo_prod_flow_migrator;
reset role;

grant hablas_evo_prod_main_migrator, hablas_evo_prod_flow_migrator to postgres;
alter default privileges for role hablas_evo_prod_flow_migrator in schema hablas_evoflow_production grant select, insert, update, delete on tables to hablas_evo_prod_flow;
alter default privileges for role hablas_evo_prod_flow_migrator in schema hablas_evoflow_production grant usage, select on sequences to hablas_evo_prod_flow;
alter default privileges for role hablas_evo_prod_main_migrator in schema public grant select, insert, update, delete on tables to hablas_evo_prod_main;
alter default privileges for role hablas_evo_prod_main_migrator in schema public grant usage, select on sequences to hablas_evo_prod_main;
revoke hablas_evo_stg_main_migrator, hablas_evo_stg_flow_migrator, hablas_evo_prod_main_migrator, hablas_evo_prod_flow_migrator from postgres;

commit;
