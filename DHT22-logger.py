import sys
import logging, logging.handlers

from Debugger.Logger import Logger
from Utility.MailSender import MailSender
from Utility.WeeklyAverages import WeeklyAverages
from Database.DbActionController import DbController
from Configurations.ConfigHandler import ConfigHandler
from Sensors.SensorDataHandler import SensorDataHandler

def main():

	# Create logger for debugging purposes
	try:
		Logger()
		logger = logging.getLogger()
	# Print to console if logger instantiation failed and terminate. Execution will fail anyway in next logging attempt
	except Exception as e: 
		print('Logger initialization failed. Error:\n{0}\nTry adding write permission directly to root (DHT22-TemperatureLogger) folder with "sudo chmod -R 777"'.format(e))
		sys.exit(0)

	#  First log entry to indicate execution has started
	logger.info("DHT22logger execution started")

	# Read configurations from config.json. If this fails, no need to run further -> terminate.
	try:
		configurationHandler = ConfigHandler()
		configurations = configurationHandler.getFullConfiguration()
	except Exception as e:
		logger.error('Failed to get configurations:\n',exc_info=True)
		sys.exit(0)

	# Instantiate dbController with configurations
	try:
		dbControl = DbController(configurations)
	except Exception as e:
		logger.error("dbController instantiation failed:\n",exc_info=True)
		sys.exit(0)

	# Instantiate mail sender
	# If mail sender instantiation fails, mail warnings cannot be send. Logger to db should work though, so no need for terminating
	try:
		mailSender = MailSender(configurations, dbControl)
		mailSenderAvailable = True
	except Exception as e:
		mailSenderAvailable = False
		logger.error('MailSender instantiation failed:\n',exc_info=True)

	# Instantiate sensorHandler and use it to read and persist readings
	try:
		SensorDataHandler(configurations,dbControl,mailSender).readAndStoreSensorReadings()
	except Exception as e:
		logger.error('Sensor data handling failed:\n',exc_info=True)
		if mailSenderAvailable:
			try:
				mailSender.sendWarningEmail("Error with sensor data handling.\nError message: {0}".format(e.message))
			except:
				logger.error('Sending warning mail failed\n',exc_info=True)

	# Weekly average temperatures - Used to check that rpi and connection is still alive
	# Check if mail sended is available, if not, no need to continue
	if mailSenderAvailable:
		logger.info("Check if weekly averages need to be sended")

		# Check if weekly average sending is enabled in configurations
		if configurationHandler.isWeeklyAveragesConfigEnabled():
			# Instantiate Weekly averages that handles configuration check etc.
			averagesSender = WeeklyAverages(configurations,dbControl,mailSender)

			# Go through configurations to check if connection check is enabled
			try:			
				# Sending is enabled and it is time to send. Execute
				averagesSender.performWeeklyAverageMailSending()
			# Log exceptions raised and send warning email
			except Exception as e:
				logger.error('Failed to check weekly averages\n',exc_info=True)
				try:
					mailSender.sendWarningEmail("Failed to send weekly averages.\nError message: {0}\nCheck debug log from Raspberry for more information".format(e.message))
				except Exception as e:
					logger.error('Failed to send email\n',exc_info=True)

	# SQL dump
	#Check if sql dump is enabled in configurations and if it is time to do the dump
	if configurationHandler.isBackupDumpConfigEnabled():
		# Yes, SQL dump is needed
		logger.info("Starting sql backup dump")
		try:
			# Call create sql backup dump
			dbControl.createSqlBackupDump()
		except Exception as e:
			logger.error('Failed to create SQL backup dump')
			if mailSenderAvailable:
				logger.error('Exception in DbBackupControl\n',exc_info=True)
				try:
					mailSender.sendWarningEmail('SQL Backup dump failed. Check debug log from raspberrypi for information')
				except Exception as e:
					logger.error('Failed to send email:\n',exc_info=True)
		logger.info("Sql backup dump finished")

	logger.info("DHT22logger execution finished\n")

if __name__ == "__main__":
	main()