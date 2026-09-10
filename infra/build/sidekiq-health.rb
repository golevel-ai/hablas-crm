# Liveness only: detect the actual Sidekiq process, not a fictitious HTTP endpoint.
# Readiness, worker heartbeat and queue age must be monitored separately.
running = Dir.glob('/proc/[0-9]*/cmdline').any? do |path|
  next false if path.split('/')[2].to_i == Process.pid
  begin
    command = File.read(path).tr("\0", ' ')
    command.match?(/\bsidekiq\b/) && !command.include?('sidekiq-health.rb')
  rescue Errno::ENOENT, Errno::EACCES
    false
  end
end
exit(running ? 0 : 1)
