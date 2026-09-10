# Compare the locked Auth schema contract with the CRM master, without Rails or a DB.
# This is structural evidence only; data migrations/seeds still require an integration test.
require 'json'

class TableContract
  attr_reader :columns, :indexes, :checks
  TYPES = %i[string text integer bigint float decimal datetime timestamp time date binary boolean json jsonb uuid inet cidr hstore virtual vector enum].freeze
  def initialize
    @columns = {}
    @indexes = []
    @checks = []
  end
  def index(columns, **options)
    @indexes << [columns, options]
  end
  def check_constraint(expression, **options)
    @checks << [expression, options]
  end
  def method_missing(type, name, **options)
    raise "Unreviewed schema DSL: #{type}" unless TYPES.include?(type)
    @columns[name] = [type, options]
  end
end

class SchemaContract
  attr_reader :tables, :foreign_keys, :version, :enums
  def initialize
    @tables = {}
    @foreign_keys = []
    @enums = {}
  end
  def define(version:, &block)
    @version = version
    instance_eval(&block)
  end
  def enable_extension(_name); end
  def create_enum(name, values)
    @enums[name] = values
  end
  def create_table(name, **options)
    table = TableContract.new
    yield table
    @tables[name] = { options: options.reject { |key, _| key == :force }, columns: table.columns, indexes: table.indexes, checks: table.checks }
  end
  def add_foreign_key(from, to, **options)
    @foreign_keys << [from, to, options]
  end
end

module ActiveRecord
  class Schema
    def self.[](_version); self; end
    def self.define(**options, &block)
      $schema_contract.define(**options, &block)
    end
  end
end

def canonical(value)
  case value
  when Proc then canonical(value.call)
  when Hash then value.sort_by { |key, _| key.to_s }.to_h.transform_values { |v| canonical(v) }
  when Array then value.map { |v| canonical(v) }
  else value
  end
end

root = File.expand_path('../..', __dir__)
contracts = %w[evo-auth-service-community evo-ai-crm-community].map do |service|
  $schema_contract = SchemaContract.new
  load File.join(root, service, 'db/schema.rb')
  $schema_contract
end
auth, crm = contracts
differences = []
auth.enums.each do |name, values|
  differences << { enum: name, issue: 'enum_contract' } unless crm.enums[name] == values
end
auth.tables.each do |name, expected|
  actual = crm.tables[name]
  if actual.nil?
    differences << { table: name, issue: 'missing_table' }
    next
  end
  differences << { table: name, issue: 'table_options' } unless canonical(actual[:options]) == canonical(expected[:options])
  differences << { table: name, issue: 'check_constraint_contract' } unless canonical(actual[:checks]) == canonical(expected[:checks])
  expected[:columns].each do |column, definition|
    differences << { table: name, column: column, issue: 'column_contract' } unless canonical(actual[:columns][column]) == canonical(definition)
  end
  expected[:indexes].each do |index|
    differences << { table: name, issue: 'missing_index_contract' } unless actual[:indexes].map { |v| canonical(v) }.include?(canonical(index))
  end
end
auth.foreign_keys.each do |key|
  differences << { table: key[0], issue: 'missing_foreign_key_contract' } unless crm.foreign_keys.map { |v| canonical(v) }.include?(canonical(key))
end
puts JSON.pretty_generate(status: differences.empty? ? 'PASS' : 'BLOCKED', scope: 'static Auth subset vs CRM schema contract',
  auth_tables: auth.tables.length, crm_tables: crm.tables.length, auth_version: auth.version, crm_version: crm.version,
  differences: differences)
exit(differences.empty? ? 0 : 2)
