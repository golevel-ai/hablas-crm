require 'json'
require 'logger'
require 'net/http'
require 'minitest/autorun'

# Exercise the generated controller without booting Rails or connecting to a DB.
module EvolutionGoConcern; end
module Rails
  def self.logger
    @logger ||= Logger.new(File::NULL)
  end
end
module Api
  module V1
    class BaseController
      def self.require_permissions(*); end
      def self.before_action(*); end
    end
    module EvolutionGo; end
  end
end

load ARGV.shift

class EvolutionGoQrcodeTest < Minitest::Test
  def test_current_and_legacy_response_contracts
    [true, false].each do |nested|
      [['qrcode', 'code'], ['Qrcode', 'Code']].each do |qr_key, code_key|
        payload = { qr_key => 'synthetic-image', code_key => 'synthetic-code' }
        payload = { 'data' => payload } if nested
        response = Net::HTTPOK.new('1.1', '200', 'OK')
        response.define_singleton_method(:body) { JSON.generate(payload) }
        http = Object.new
        [:use_ssl=, :open_timeout=, :read_timeout=].each do |setter|
          http.define_singleton_method(setter) { |_value| }
        end
        http.define_singleton_method(:request) do |request|
          raise 'Incorrect instance authentication' unless request['apikey'] == 'synthetic-token'
          response
        end
        Net::HTTP.stub(:new, http) do
          actual = Api::V1::EvolutionGo::QrcodesController.new.send(
            :get_qrcode_go, 'https://example.invalid', 'synthetic-token'
          )
          assert_equal({ base64: 'synthetic-image', code: 'synthetic-code', connected: false }, actual)
        end
      end
    end
  end
end
