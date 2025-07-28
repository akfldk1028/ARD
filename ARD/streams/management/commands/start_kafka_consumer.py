import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from streams.consumers import AriaKafkaConsumer

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start Kafka consumer for Aria data streams'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--topics',
            nargs='+',
            help='Specific topics to consume (default: all topics)'
        )
        parser.add_argument(
            '--consumer-group',
            default='aria-django-consumer',
            help='Kafka consumer group name'
        )
        parser.add_argument(
            '--bootstrap-servers',
            default='localhost:9092',
            help='Kafka bootstrap servers'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Starting Aria Kafka Consumer...')
        
        consumer = AriaKafkaConsumer(
            bootstrap_servers=options['bootstrap_servers'],
            consumer_group=options['consumer_group']
        )
        
        try:
            # Run the async consumer
            asyncio.run(consumer.start_consuming(topics=options.get('topics')))
        except KeyboardInterrupt:
            self.stdout.write('\nShutting down consumer...')
            consumer.stop_consuming()
            consumer.close()
        except Exception as e:
            self.stderr.write(f'Consumer error: {e}')
        finally:
            self.stdout.write('Consumer stopped.')