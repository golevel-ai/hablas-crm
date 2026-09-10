# First install only. Called by the operator under the shared database lock.
require 'digest'
owner = ENV.fetch('EVO_BOOTSTRAP_OWNER')
raise 'Wrong deployment owner' unless owner == 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9'
connection = ActiveRecord::Base.connection
raise 'Unexpected schema' unless connection.select_value('SELECT current_schema()') == 'public'
schema = Rails.root.join('db/schema.rb')
stamp = owner + '/' + Digest::SHA256.file(schema).hexdigest
marker_key = 'hablas_evo_bootstrap_source'
table_count = connection.select_value("SELECT count(*) FROM pg_tables WHERE schemaname='public'").to_i
if table_count.zero?
  raise 'Unknown existing application enum' if connection.select_value("SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' AND t.typname='contact_type_enum'").to_i.positive?
  ActiveRecord::Tasks::DatabaseTasks.load_schema_current(:ruby, schema.to_s)
  connection = ActiveRecord::Base.connection
  connection.execute("INSERT INTO ar_internal_metadata(key,value,created_at,updated_at) VALUES (#{connection.quote(marker_key)},#{connection.quote(stamp)},now(),now())")
  puts 'PASS: CRM master schema loaded into previously empty public schema'
else
  raise 'Existing schema requires ownership and source marker' unless connection.data_source_exists?('ar_internal_metadata')
  current = connection.select_value("SELECT value FROM ar_internal_metadata WHERE key=#{connection.quote(marker_key)}")
  raise 'Existing schema is not this bootstrap release; use controlled incremental migrations' unless current == stamp
  puts 'PASS: owned bootstrap source already present; schema was not reloaded'
end
