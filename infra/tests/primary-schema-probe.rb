# Executed only in disposable CI containers. insert_all bypasses mail/webhook callbacks.
raise 'CI fixture only' unless ENV['INFRA_LOCAL_SCHEMA_TEST'] == 'true'
user_id = '00000000-0000-4000-8000-000000000001'
phase = ENV.fetch('INFRA_TEST_PHASE')
case phase
when 'crm-write'
  User.insert_all!([{ id: user_id, name: 'Infrastructure CI', email: 'infra-ci@example.invalid',
                     uid: 'infra-ci@example.invalid', provider: 'email',
                     created_at: Time.current, updated_at: Time.current }])
  record = InstallationConfig.create!(name: 'INFRA_CI_SECRET', serialized_value: { 'value' => 'local-only-probe' })
  raise 'CRM did not encrypt the configuration' if record.reload.serialized_value['value'] == 'local-only-probe'
  UserTour.create!(user_id: user_id, tour_key: 'crm-completed', completed_at: Time.current, status: 'completed')
when 'auth-read-write'
  raise 'Auth cannot decrypt CRM config' unless InstallationConfig.find_by!(name: 'INFRA_CI_SECRET').value == 'local-only-probe'
  UserTour.create!(user_id: user_id, tour_key: 'auth-completed', completed_at: Time.current, status: 'completed')
when 'crm-read'
  keys = UserTour.where(user_id: user_id).pluck(:tour_key).sort
  raise 'Shared tour persistence failed' unless keys == %w[auth-completed crm-completed]
else
  raise 'Unexpected test phase'
end
puts "PASS: #{phase} shared-schema contract"
