#!/usr/bin/env ruby
# Admin panel server for TaskJuggler Docker Compose
#
# Provides a simple web interface on port 9090 with buttons to trigger:
# - Project compilation (rebuild reports)
# - Timesheet collection (flush mail queue)
# - Send reminder emails
#
# Runs inside the tj-web container alongside tj3d/tj3webd.

require 'webrick'
require 'json'
require 'open3'

ADMIN_PORT = 9090
PROJECT_FILE = ENV.fetch('TJ_PROJECT_FILE', 'project.tjp')
PROJECT_DIR = '/app/project'
REPORT_DIR = '/app/reports'

# Serve the admin HTML page
admin_page = File.read(File.join(__dir__, 'index.html'))

server = WEBrick::HTTPServer.new(
  Port: ADMIN_PORT,
  Logger: WEBrick::Log.new($stdout, WEBrick::Log::INFO),
  AccessLog: []
)

# GET / — serve admin page
server.mount_proc('/') do |req, res|
  if req.request_method == 'GET'
    res['Content-Type'] = 'text/html'
    res.body = admin_page
  else
    res.status = 405
    res.body = 'Method not allowed'
  end
end

# POST /api/rebuild — trigger project compilation
server.mount_proc('/api/rebuild') do |req, res|
  res['Content-Type'] = 'application/json'

  unless req.request_method == 'POST'
    res.status = 405
    res.body = JSON.generate({ success: false, message: 'Method not allowed' })
    next
  end

  # Clear previous reports
  Dir.glob(File.join(REPORT_DIR, '*')).each { |f| File.delete(f) if File.file?(f) }

  # Run tj3 compilation
  cmd = "tj3 -o #{REPORT_DIR} #{File.join(PROJECT_DIR, PROJECT_FILE)}"
  stdout, stderr, status = Open3.capture3(cmd)

  if status.success?
    report_count = Dir.glob(File.join(REPORT_DIR, '*')).count { |f| File.file?(f) }
    res.body = JSON.generate({
      success: true,
      message: "Compilation completed: #{report_count} reports generated"
    })
  else
    res.status = 500
    res.body = JSON.generate({
      success: false,
      message: "Compilation failed (exit code #{status.exitstatus})",
      details: stderr.to_s[0, 1000]
    })
  end
end

# POST /api/collect-timesheets — trigger timesheet collection
server.mount_proc('/api/collect-timesheets') do |req, res|
  res['Content-Type'] = 'application/json'

  unless req.request_method == 'POST'
    res.status = 405
    res.body = JSON.generate({ success: false, message: 'Method not allowed' })
    next
  end

  # Timesheets are collected by the mail service. From tj-web we can't
  # directly trigger tj-mail, but we can report the current timesheet status.
  timesheet_dir = File.join(PROJECT_DIR, 'timesheets')
  if Dir.exist?(timesheet_dir)
    files = Dir.glob(File.join(timesheet_dir, '*.tji'))
    res.body = JSON.generate({
      success: true,
      message: "#{files.length} timesheet(s) currently in project. Collection is handled automatically by the cron service."
    })
  else
    res.body = JSON.generate({
      success: true,
      message: "Timesheet directory not found. Collection is handled automatically by the cron service."
    })
  end
end

# POST /api/send-reminders — info about reminders
server.mount_proc('/api/send-reminders') do |req, res|
  res['Content-Type'] = 'application/json'

  unless req.request_method == 'POST'
    res.status = 405
    res.body = JSON.generate({ success: false, message: 'Method not allowed' })
    next
  end

  res.body = JSON.generate({
    success: true,
    message: "Reminder emails are sent automatically by the cron service on the configured schedule. Use 'docker compose exec tj-mail /app/scripts/send-reminders.sh' to trigger manually."
  })
end

# GET /api/status — system status
server.mount_proc('/api/status') do |req, res|
  res['Content-Type'] = 'application/json'

  report_count = Dir.glob(File.join(REPORT_DIR, '**', '*.html')).length
  project_exists = File.exist?(File.join(PROJECT_DIR, PROJECT_FILE))
  timesheet_dir = File.join(PROJECT_DIR, 'timesheets')
  timesheet_count = Dir.exist?(timesheet_dir) ? Dir.glob(File.join(timesheet_dir, '*.tji')).length : 0

  res.body = JSON.generate({
    project_file: PROJECT_FILE,
    project_exists: project_exists,
    report_count: report_count,
    timesheet_count: timesheet_count
  })
end

trap('INT') { server.shutdown }
trap('TERM') { server.shutdown }

$stdout.puts "[tj-web] [#{Time.now.utc.strftime('%Y-%m-%dT%H:%M:%SZ')}] [INFO] Admin panel started on port #{ADMIN_PORT}"
server.start
