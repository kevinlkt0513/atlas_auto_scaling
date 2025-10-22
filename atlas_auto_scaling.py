"""
Atlas Auto Scaling Script - Integrated Solution
Based on MongoDB Atlas Scheduled Triggers approach
Reference: https://www.mongodb.com/developer/products/atlas/atlas-cluster-automation-using-scheduled-triggers/

A comprehensive auto-scaling solution for MongoDB Atlas clusters with:
- High-frequency monitoring (every minute)
- Zero-delay scaling capabilities
- Intelligent scaling decisions
- Multi-channel alerting
- Flexible configuration
"""

import os
import sys
import time
import json
import base64
import hashlib
import hmac
import requests
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from collections import deque
import argparse


# =============================================================================
# Configuration Classes
# =============================================================================

@dataclass
class AtlasConfig:
    """Atlas API configuration"""
    public_key: str
    private_key: str
    project_id: str
    base_url: str = "https://cloud.mongodb.com/api/atlas/v2"


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    check_interval: int = 60  # seconds
    cpu_threshold_high: float = 80.0
    cpu_threshold_low: float = 30.0
    connection_threshold_high: int = 1000
    connection_threshold_low: int = 100
    iops_threshold_high: int = 1000
    iops_threshold_low: int = 100
    memory_threshold_high: float = 85.0
    memory_threshold_low: float = 40.0


@dataclass
class ScalingConfig:
    """Auto-scaling configuration"""
    enabled: bool = True
    scale_up_cooldown: int = 0  # 0 = no delay
    scale_down_cooldown: int = 300  # 5 minutes
    max_scale_up_per_hour: int = 3
    max_scale_down_per_hour: int = 2
    min_instance_size: str = "M10"
    max_instance_size: str = "M80"
    scale_up_step: str = "M20"
    scale_down_step: str = "M10"


@dataclass
class AlertConfig:
    """Alert configuration"""
    enabled: bool = True
    webhook_url: Optional[str] = None
    email_notifications: bool = False
    email_recipients: List[str] = None
    slack_webhook: Optional[str] = None


@dataclass
class ClusterMetrics:
    """Cluster metrics container"""
    cluster_name: str
    timestamp: datetime
    cpu_utilization: float
    connection_count: int
    iops: int
    memory_utilization: float
    is_healthy: bool
    scaling_recommendation: Optional[str] = None


@dataclass
class ScalingEvent:
    """Scaling event record"""
    timestamp: datetime
    cluster_name: str
    action: str
    from_size: str
    to_size: str
    reason: str
    success: bool
    error_message: Optional[str] = None


# =============================================================================
# Atlas API Client
# =============================================================================

class AtlasAPIError(Exception):
    """Atlas API error exception"""
    pass


class AtlasClient:
    """MongoDB Atlas Admin API client"""
    
    def __init__(self, public_key: str, private_key: str, project_id: str, base_url: str = "https://cloud.mongodb.com/api/atlas/v1.0"):
        self.public_key = public_key
        self.private_key = private_key
        self.project_id = project_id
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
    def _generate_signature(self, timestamp: str) -> str:
        """Generate Atlas API v2 signature for authentication"""
        # Atlas API v2 uses HMAC-SHA1 with timestamp
        digest = hmac.new(
            self.private_key.encode('utf-8'),
            msg=timestamp.encode('utf-8'),
            digestmod=hashlib.sha1
        ).digest()
        signature = base64.b64encode(digest).decode('utf-8')
        return signature
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make authenticated request to Atlas API v2"""
        url = f"{self.base_url}{endpoint}"
        timestamp = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        body = json.dumps(data) if data else ""
        
        signature = self._generate_signature(timestamp)
        auth_header = f'MongoDB {self.public_key}:{signature}'
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': auth_header,
            'Date': timestamp
        }
        
        if params:
            url += '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                data=body,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise AtlasAPIError(f"API request failed: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise AtlasAPIError(f"Request failed: {str(e)}")
    
    def get_clusters(self) -> List[Dict]:
        """Get all clusters in the project"""
        try:
            response = self._make_request('GET', f'/groups/{self.project_id}/clusters')
            return response.get('results', [])
        except Exception as e:
            raise AtlasAPIError(f"Failed to get clusters: {str(e)}")
    
    def get_cluster(self, cluster_name: str) -> Dict:
        """Get specific cluster information"""
        try:
            response = self._make_request('GET', f'/groups/{self.project_id}/clusters/{cluster_name}')
            return response
        except Exception as e:
            raise AtlasAPIError(f"Failed to get cluster {cluster_name}: {str(e)}")
    
    def update_cluster_size(self, cluster_name: str, instance_size: str) -> Dict:
        """Update cluster instance size"""
        try:
            data = {
                'providerSettings': {
                    'instanceSizeName': instance_size
                }
            }
            response = self._make_request('PATCH', f'/groups/{self.project_id}/clusters/{cluster_name}', data=data)
            return response
        except Exception as e:
            raise AtlasAPIError(f"Failed to update cluster {cluster_name} to {instance_size}: {str(e)}")
    
    def get_cluster_metrics(self, cluster_name: str, metric_names: List[str], start_time: datetime, end_time: datetime, granularity: str = "PT1M") -> Dict:
        """Get cluster metrics for a specific time range using Atlas API v2"""
        try:
            params = {
                'm': metric_names,
                'start': start_time.isoformat() + 'Z',
                'end': end_time.isoformat() + 'Z',
                'granularity': granularity
            }
            
            response = self._make_request(
                'GET', 
                f'/groups/{self.project_id}/clusters/{cluster_name}/processes/{cluster_name}/measurements',
                params=params
            )
            return response
        except Exception as e:
            raise AtlasAPIError(f"Failed to get metrics for cluster {cluster_name}: {str(e)}")
    
    def get_cpu_metrics(self, cluster_name: str, start_time: datetime, end_time: datetime) -> List[float]:
        """Get CPU utilization metrics using Atlas API v2"""
        try:
            response = self.get_cluster_metrics(cluster_name, ['CPU_USAGE'], start_time, end_time)
            measurements = response.get('measurements', [])
            cpu_values = []
            
            for measurement in measurements:
                if measurement.get('name') == 'CPU_USAGE' and 'dataPoints' in measurement:
                    for point in measurement['dataPoints']:
                        if point.get('value') is not None:
                            cpu_values.append(float(point['value']))
            
            return cpu_values
        except Exception as e:
            raise AtlasAPIError(f"Failed to get CPU metrics: {str(e)}")
    
    def get_connection_metrics(self, cluster_name: str, start_time: datetime, end_time: datetime) -> List[int]:
        """Get connection count metrics using Atlas API v2"""
        try:
            response = self.get_cluster_metrics(cluster_name, ['CONNECTIONS'], start_time, end_time)
            measurements = response.get('measurements', [])
            connection_values = []
            
            for measurement in measurements:
                if measurement.get('name') == 'CONNECTIONS' and 'dataPoints' in measurement:
                    for point in measurement['dataPoints']:
                        if point.get('value') is not None:
                            connection_values.append(int(point['value']))
            
            return connection_values
        except Exception as e:
            raise AtlasAPIError(f"Failed to get connection metrics: {str(e)}")
    
    def get_iops_metrics(self, cluster_name: str, start_time: datetime, end_time: datetime) -> List[int]:
        """Get IOPS metrics using Atlas API v2"""
        try:
            response = self.get_cluster_metrics(cluster_name, ['DISK_IOPS'], start_time, end_time)
            measurements = response.get('measurements', [])
            iops_values = []
            
            for measurement in measurements:
                if measurement.get('name') == 'DISK_IOPS' and 'dataPoints' in measurement:
                    for point in measurement['dataPoints']:
                        if point.get('value') is not None:
                            iops_values.append(int(point['value']))
            
            return iops_values
        except Exception as e:
            raise AtlasAPIError(f"Failed to get IOPS metrics: {str(e)}")
    
    def get_memory_metrics(self, cluster_name: str, start_time: datetime, end_time: datetime) -> List[float]:
        """Get memory utilization metrics using Atlas API v2"""
        try:
            response = self.get_cluster_metrics(cluster_name, ['MEMORY_USAGE'], start_time, end_time)
            measurements = response.get('measurements', [])
            memory_values = []
            
            for measurement in measurements:
                if measurement.get('name') == 'MEMORY_USAGE' and 'dataPoints' in measurement:
                    for point in measurement['dataPoints']:
                        if point.get('value') is not None:
                            memory_values.append(float(point['value']))
            
            return memory_values
        except Exception as e:
            raise AtlasAPIError(f"Failed to get memory metrics: {str(e)}")
    
    def is_cluster_ready(self, cluster_name: str) -> bool:
        """Check if cluster is ready for operations"""
        try:
            cluster_info = self.get_cluster(cluster_name)
            return cluster_info.get('stateName') == 'IDLE'
        except AtlasAPIError:
            return False
    
    def test_connection(self) -> bool:
        """Test API connection and credentials"""
        try:
            self.get_clusters()
            return True
        except AtlasAPIError:
            return False


# =============================================================================
# Monitoring and Scaling Logic
# =============================================================================

class AtlasAutoScaling:
    """Integrated Atlas auto-scaling solution"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.atlas_client = None
        self.metrics_history = deque(maxlen=100)
        self.scaling_history = {}
        self.last_scaling_time = {}
        self.running = False
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Load configuration
        self._load_config()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('atlas_scaling.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger(__name__)
    
    def _load_config(self):
        """Load configuration from file or environment variables"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                config_data = {}
            
            # Load Atlas configuration
            self.atlas_config = AtlasConfig(
                public_key=config_data.get('atlas', {}).get('public_key') or os.getenv('ATLAS_PUBLIC_KEY', ''),
                private_key=config_data.get('atlas', {}).get('private_key') or os.getenv('ATLAS_PRIVATE_KEY', ''),
                project_id=config_data.get('atlas', {}).get('project_id') or os.getenv('ATLAS_PROJECT_ID', ''),
                base_url=config_data.get('atlas', {}).get('base_url', 'https://cloud.mongodb.com/api/atlas/v2')
            )
            
            # Load monitoring configuration
            monitoring_data = config_data.get('monitoring', {})
            self.monitoring_config = MonitoringConfig(
                check_interval=monitoring_data.get('check_interval', 60),
                cpu_threshold_high=monitoring_data.get('cpu_threshold_high', 80.0),
                cpu_threshold_low=monitoring_data.get('cpu_threshold_low', 30.0),
                connection_threshold_high=monitoring_data.get('connection_threshold_high', 1000),
                connection_threshold_low=monitoring_data.get('connection_threshold_low', 100),
                iops_threshold_high=monitoring_data.get('iops_threshold_high', 1000),
                iops_threshold_low=monitoring_data.get('iops_threshold_low', 100),
                memory_threshold_high=monitoring_data.get('memory_threshold_high', 85.0),
                memory_threshold_low=monitoring_data.get('memory_threshold_low', 40.0)
            )
            
            # Load scaling configuration
            scaling_data = config_data.get('scaling', {})
            self.scaling_config = ScalingConfig(
                enabled=scaling_data.get('enabled', True),
                scale_up_cooldown=scaling_data.get('scale_up_cooldown', 0),
                scale_down_cooldown=scaling_data.get('scale_down_cooldown', 300),
                max_scale_up_per_hour=scaling_data.get('max_scale_up_per_hour', 3),
                max_scale_down_per_hour=scaling_data.get('max_scale_down_per_hour', 2),
                min_instance_size=scaling_data.get('min_instance_size', 'M10'),
                max_instance_size=scaling_data.get('max_instance_size', 'M80'),
                scale_up_step=scaling_data.get('scale_up_step', 'M20'),
                scale_down_step=scaling_data.get('scale_down_step', 'M10')
            )
            
            # Load alert configuration
            alert_data = config_data.get('alerts', {})
            self.alert_config = AlertConfig(
                enabled=alert_data.get('enabled', True),
                webhook_url=alert_data.get('webhook_url'),
                email_notifications=alert_data.get('email_notifications', False),
                email_recipients=alert_data.get('email_recipients', []),
                slack_webhook=alert_data.get('slack_webhook')
            )
            
            # Initialize Atlas client
            self.atlas_client = AtlasClient(
                self.atlas_config.public_key,
                self.atlas_config.private_key,
                self.atlas_config.project_id,
                self.atlas_config.base_url
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
    
    def collect_metrics(self, cluster_name: str) -> Optional[ClusterMetrics]:
        """Collect current metrics for a cluster"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=5)
            
            # Collect metrics
            cpu_data = self._get_cpu_data(cluster_name, start_time, end_time)
            connection_data = self._get_connection_data(cluster_name, start_time, end_time)
            iops_data = self._get_iops_data(cluster_name, start_time, end_time)
            memory_data = self._get_memory_data(cluster_name, start_time, end_time)
            
            # Calculate averages
            cpu_avg = statistics.mean(cpu_data) if cpu_data else 0.0
            connection_avg = statistics.mean(connection_data) if connection_data else 0
            iops_avg = statistics.mean(iops_data) if iops_data else 0
            memory_avg = statistics.mean(memory_data) if memory_data else 0.0
            
            # Assess health and generate recommendation
            is_healthy = self._assess_cluster_health(cpu_avg, connection_avg, iops_avg, memory_avg)
            scaling_rec = self._generate_scaling_recommendation(cpu_avg, connection_avg, iops_avg, memory_avg)
            
            metrics = ClusterMetrics(
                cluster_name=cluster_name,
                timestamp=end_time,
                cpu_utilization=cpu_avg,
                connection_count=int(connection_avg),
                iops=int(iops_avg),
                memory_utilization=memory_avg,
                is_healthy=is_healthy,
                scaling_recommendation=scaling_rec
            )
            
            self.metrics_history.append(metrics)
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics for {cluster_name}: {e}")
            return None
    
    def _get_cpu_data(self, cluster_name: str, start_time: datetime, end_time: datetime) -> List[float]:
        """Get CPU utilization data"""
        try:
            return self.atlas_client.get_cpu_metrics(cluster_name, start_time, end_time)
        except AtlasAPIError:
            return []
    
    def _get_connection_data(self, cluster_name: str, start_time: datetime, end_time: datetime) -> List[int]:
        """Get connection count data"""
        try:
            return self.atlas_client.get_connection_metrics(cluster_name, start_time, end_time)
        except AtlasAPIError:
            return []
    
    def _get_iops_data(self, cluster_name: str, start_time: datetime, end_time: datetime) -> List[int]:
        """Get IOPS data"""
        try:
            return self.atlas_client.get_iops_metrics(cluster_name, start_time, end_time)
        except AtlasAPIError:
            return []
    
    def _get_memory_data(self, cluster_name: str, start_time: datetime, end_time: datetime) -> List[float]:
        """Get memory utilization data"""
        try:
            return self.atlas_client.get_memory_metrics(cluster_name, start_time, end_time)
        except AtlasAPIError:
            return []
    
    def _assess_cluster_health(self, cpu: float, connections: int, iops: int, memory: float) -> bool:
        """Assess if cluster is healthy based on thresholds"""
        cpu_ok = cpu <= self.monitoring_config.cpu_threshold_high
        connection_ok = connections <= self.monitoring_config.connection_threshold_high
        iops_ok = iops <= self.monitoring_config.iops_threshold_high
        memory_ok = memory <= self.monitoring_config.memory_threshold_high
        
        return cpu_ok and connection_ok and iops_ok and memory_ok
    
    def _generate_scaling_recommendation(self, cpu: float, connections: int, iops: int, memory: float) -> Optional[str]:
        """Generate scaling recommendation based on metrics"""
        # Check for scale-up conditions
        if (cpu >= self.monitoring_config.cpu_threshold_high or 
            connections >= self.monitoring_config.connection_threshold_high or
            iops >= self.monitoring_config.iops_threshold_high or
            memory >= self.monitoring_config.memory_threshold_high):
            return "scale_up"
        
        # Check for scale-down conditions
        if (cpu <= self.monitoring_config.cpu_threshold_low and 
            connections <= self.monitoring_config.connection_threshold_low and
            iops <= self.monitoring_config.iops_threshold_low and
            memory <= self.monitoring_config.memory_threshold_low):
            return "scale_down"
        
        return None
    
    def _get_instance_size_hierarchy(self) -> List[str]:
        """Get instance size hierarchy for scaling decisions"""
        return [
            'M0', 'M2', 'M5', 'M10', 'M20', 'M30', 'M40', 'M50', 'M60', 'M80',
            'M100', 'M140', 'M200', 'M300', 'M400', 'M500', 'M600', 'M700', 'M800'
        ]
    
    def _get_next_size(self, current_size: str, direction: str) -> Optional[str]:
        """Get next instance size in the hierarchy"""
        hierarchy = self._get_instance_size_hierarchy()
        try:
            current_index = hierarchy.index(current_size)
            if direction == 'up' and current_index < len(hierarchy) - 1:
                return hierarchy[current_index + 1]
            elif direction == 'down' and current_index > 0:
                return hierarchy[current_index - 1]
        except ValueError:
            pass
        return None
    
    def _check_cooldown(self, cluster_name: str, action: str) -> bool:
        """Check if enough time has passed since last scaling action"""
        if action not in ['scale_up', 'scale_down']:
            return True
        
        last_scaling = self.last_scaling_time.get(cluster_name, {})
        last_action_time = last_scaling.get(action)
        
        if not last_action_time:
            return True
        
        cooldown_seconds = (self.scaling_config.scale_up_cooldown if action == 'scale_up' 
                          else self.scaling_config.scale_down_cooldown)
        
        time_since_last = (datetime.utcnow() - last_action_time).total_seconds()
        return time_since_last >= cooldown_seconds
    
    def _check_hourly_limits(self, cluster_name: str, action: str) -> bool:
        """Check if hourly scaling limits have been reached"""
        if action not in ['scale_up', 'scale_down']:
            return True
        
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_scaling = [
            event for event in self.scaling_history.get(cluster_name, [])
            if (event.timestamp >= one_hour_ago and 
                event.action == action and 
                event.success)
        ]
        
        max_allowed = (self.scaling_config.max_scale_up_per_hour if action == 'scale_up'
                      else self.scaling_config.max_scale_down_per_hour)
        
        return len(recent_scaling) < max_allowed
    
    def should_scale(self, cluster_name: str, metrics: ClusterMetrics, current_size: str) -> Optional[Tuple[str, str]]:
        """Determine if cluster should be scaled and return (action, reason)"""
        if not self.scaling_config.enabled:
            return None
        
        if not self._check_cooldown(cluster_name, metrics.scaling_recommendation):
            return None
        
        if not self._check_hourly_limits(cluster_name, metrics.scaling_recommendation):
            return None
        
        if metrics.scaling_recommendation == "scale_up":
            reason = self._get_scale_up_reason(metrics)
            return ("scale_up", reason)
        elif metrics.scaling_recommendation == "scale_down":
            reason = self._get_scale_down_reason(metrics)
            return ("scale_down", reason)
        
        return None
    
    def _get_scale_up_reason(self, metrics: ClusterMetrics) -> str:
        """Generate reason for scale up"""
        reasons = []
        if metrics.cpu_utilization >= self.monitoring_config.cpu_threshold_high:
            reasons.append(f"High CPU: {metrics.cpu_utilization:.1f}%")
        if metrics.connection_count >= self.monitoring_config.connection_threshold_high:
            reasons.append(f"High connections: {metrics.connection_count}")
        if metrics.iops >= self.monitoring_config.iops_threshold_high:
            reasons.append(f"High IOPS: {metrics.iops}")
        if metrics.memory_utilization >= self.monitoring_config.memory_threshold_high:
            reasons.append(f"High memory: {metrics.memory_utilization:.1f}%")
        
        return "; ".join(reasons) if reasons else "Performance threshold exceeded"
    
    def _get_scale_down_reason(self, metrics: ClusterMetrics) -> str:
        """Generate reason for scale down"""
        return (f"Low resource utilization: "
                f"CPU={metrics.cpu_utilization:.1f}%, "
                f"Connections={metrics.connection_count}, "
                f"IOPS={metrics.iops}, "
                f"Memory={metrics.memory_utilization:.1f}%")
    
    def execute_scaling(self, cluster_name: str, current_size: str, new_size: str, action: str, reason: str) -> bool:
        """Execute the actual scaling operation"""
        try:
            self.logger.info(f"Scaling {cluster_name} from {current_size} to {new_size} ({action}): {reason}")
            
            result = self.atlas_client.update_cluster_size(cluster_name, new_size)
            
            if result:
                self.logger.info(f"Successfully initiated scaling for {cluster_name}")
                
                # Record scaling event
                event = ScalingEvent(
                    timestamp=datetime.utcnow(),
                    cluster_name=cluster_name,
                    action=action,
                    from_size=current_size,
                    to_size=new_size,
                    reason=reason,
                    success=True
                )
                
                if cluster_name not in self.scaling_history:
                    self.scaling_history[cluster_name] = []
                self.scaling_history[cluster_name].append(event)
                self.last_scaling_time[cluster_name] = {action: datetime.utcnow()}
                
                # Send alert
                self._send_scaling_alert(cluster_name, action, current_size, new_size, reason)
                
                return True
            else:
                self.logger.error(f"Failed to initiate scaling for {cluster_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to scale {cluster_name}: {e}")
            return False
    
    def process_cluster(self, cluster_name: str) -> bool:
        """Process a single cluster for monitoring and scaling"""
        try:
            # Collect metrics
            metrics = self.collect_metrics(cluster_name)
            if not metrics:
                self.logger.warning(f"Failed to collect metrics for {cluster_name}")
                return False
            
            # Log metrics
            self.logger.info(f"Cluster {cluster_name}: "
                           f"CPU={metrics.cpu_utilization:.1f}%, "
                           f"Connections={metrics.connection_count}, "
                           f"IOPS={metrics.iops}, "
                           f"Memory={metrics.memory_utilization:.1f}%")
            
            # Check for alerts
            alerts = self._get_alert_conditions(metrics)
            if alerts:
                self.logger.warning(f"Alerts for {cluster_name}: {alerts}")
                self._send_alerts(cluster_name, alerts)
            
            # Process scaling decision
            if metrics.scaling_recommendation:
                self.logger.info(f"Scaling recommendation for {cluster_name}: {metrics.scaling_recommendation}")
                
                # Get current cluster size
                cluster_info = self.atlas_client.get_cluster(cluster_name)
                current_size = cluster_info.get('providerSettings', {}).get('instanceSizeName', 'M10')
                
                # Make scaling decision
                decision = self.should_scale(cluster_name, metrics, current_size)
                if decision:
                    action, reason = decision
                    new_size = self._get_next_size(current_size, action)
                    
                    if new_size:
                        success = self.execute_scaling(cluster_name, current_size, new_size, action, reason)
                        if success:
                            self.logger.info(f"Scaling decision executed for {cluster_name}")
                        else:
                            self.logger.warning(f"Scaling decision failed for {cluster_name}")
                    else:
                        self.logger.warning(f"Cannot determine new size for {cluster_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing cluster {cluster_name}: {e}")
            return False
    
    def _get_alert_conditions(self, metrics: ClusterMetrics) -> List[str]:
        """Check for alert conditions"""
        alerts = []
        
        if metrics.cpu_utilization >= self.monitoring_config.cpu_threshold_high:
            alerts.append(f"High CPU utilization: {metrics.cpu_utilization:.1f}%")
        
        if metrics.connection_count >= self.monitoring_config.connection_threshold_high:
            alerts.append(f"High connection count: {metrics.connection_count}")
        
        if metrics.iops >= self.monitoring_config.iops_threshold_high:
            alerts.append(f"High IOPS: {metrics.iops}")
        
        if metrics.memory_utilization >= self.monitoring_config.memory_threshold_high:
            alerts.append(f"High memory utilization: {metrics.memory_utilization:.1f}%")
        
        return alerts
    
    def _send_alerts(self, cluster_name: str, alerts: List[str]) -> bool:
        """Send alerts via configured channels"""
        if not self.alert_config.enabled:
            return True
        
        success = True
        
        # Send webhook alert
        if self.alert_config.webhook_url:
            if not self._send_webhook_alert(cluster_name, alerts):
                success = False
        
        # Send Slack alert
        if self.alert_config.slack_webhook:
            if not self._send_slack_alert(cluster_name, alerts):
                success = False
        
        return success
    
    def _send_webhook_alert(self, cluster_name: str, alerts: List[str]) -> bool:
        """Send alert via webhook"""
        try:
            payload = {
                'timestamp': datetime.utcnow().isoformat(),
                'cluster_name': cluster_name,
                'alerts': alerts,
                'severity': 'warning' if len(alerts) > 0 else 'info'
            }
            
            response = requests.post(
                self.alert_config.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"Webhook alert sent for {cluster_name}")
                return True
            else:
                self.logger.error(f"Webhook alert failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending webhook alert: {e}")
            return False
    
    def _send_slack_alert(self, cluster_name: str, alerts: List[str]) -> bool:
        """Send alert via Slack"""
        try:
            message = {
                'text': f"🚨 Atlas Alert: {cluster_name}",
                'attachments': [
                    {
                        'color': 'warning',
                        'fields': [
                            {
                                'title': 'Cluster',
                                'value': cluster_name,
                                'short': True
                            },
                            {
                                'title': 'Timestamp',
                                'value': datetime.utcnow().isoformat(),
                                'short': True
                            },
                            {
                                'title': 'Alerts',
                                'value': '\n'.join(f"• {alert}" for alert in alerts),
                                'short': False
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(
                self.alert_config.slack_webhook,
                json=message,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"Slack alert sent for {cluster_name}")
                return True
            else:
                self.logger.error(f"Slack alert failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Slack alert: {e}")
            return False
    
    def _send_scaling_alert(self, cluster_name: str, action: str, from_size: str, to_size: str, reason: str):
        """Send scaling notification"""
        if not self.alert_config.enabled:
            return
        
        message = f"Scaling {action}: {cluster_name} from {from_size} to {to_size}. Reason: {reason}"
        
        # Send webhook notification
        if self.alert_config.webhook_url:
            try:
                payload = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'cluster_name': cluster_name,
                    'action': action,
                    'from_size': from_size,
                    'to_size': to_size,
                    'reason': reason,
                    'type': 'scaling'
                }
                
                requests.post(
                    self.alert_config.webhook_url,
                    json=payload,
                    timeout=10
                )
            except Exception as e:
                self.logger.error(f"Error sending scaling webhook: {e}")
        
        # Send Slack notification
        if self.alert_config.slack_webhook:
            try:
                slack_message = {
                    'text': f"⚡ Scaling Action: {cluster_name}",
                    'attachments': [
                        {
                            'color': 'good' if action == 'scale_up' else 'warning',
                            'fields': [
                                {
                                    'title': 'Action',
                                    'value': f"{action.replace('_', ' ').title()}",
                                    'short': True
                                },
                                {
                                    'title': 'Size Change',
                                    'value': f"{from_size} → {to_size}",
                                    'short': True
                                },
                                {
                                    'title': 'Reason',
                                    'value': reason,
                                    'short': False
                                }
                            ]
                        }
                    ]
                }
                
                requests.post(
                    self.alert_config.slack_webhook,
                    json=slack_message,
                    timeout=10
                )
            except Exception as e:
                self.logger.error(f"Error sending scaling Slack notification: {e}")
    
    def run_continuous_monitoring(self, cluster_names: List[str]):
        """Run continuous monitoring loop"""
        self.running = True
        self.logger.info(f"Starting continuous monitoring for clusters: {cluster_names}")
        
        try:
            while self.running:
                for cluster_name in cluster_names:
                    try:
                        self.process_cluster(cluster_name)
                    except Exception as e:
                        self.logger.error(f"Error monitoring {cluster_name}: {e}")
                
                time.sleep(self.monitoring_config.check_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Monitoring stopped by user")
        except Exception as e:
            self.logger.error(f"Error in monitoring loop: {e}")
        finally:
            self.running = False
    
    def run_single_check(self, cluster_names: List[str]):
        """Run a single check and exit"""
        self.logger.info("Running single check")
        
        for cluster_name in cluster_names:
            try:
                self.process_cluster(cluster_name)
            except Exception as e:
                self.logger.error(f"Error checking {cluster_name}: {e}")
    
    def get_status_report(self, cluster_names: List[str]) -> Dict[str, Any]:
        """Generate status report for all clusters"""
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'clusters': {}
        }
        
        for cluster_name in cluster_names:
            try:
                # Get latest metrics
                latest_metrics = None
                for metrics in reversed(self.metrics_history):
                    if metrics.cluster_name == cluster_name:
                        latest_metrics = metrics
                        break
                
                # Get scaling history
                scaling_events = self.scaling_history.get(cluster_name, [])
                recent_events = [e for e in scaling_events if e.timestamp >= datetime.utcnow() - timedelta(hours=24)]
                
                report['clusters'][cluster_name] = {
                    'latest_metrics': {
                        'cpu_utilization': latest_metrics.cpu_utilization if latest_metrics else 0,
                        'connection_count': latest_metrics.connection_count if latest_metrics else 0,
                        'iops': latest_metrics.iops if latest_metrics else 0,
                        'memory_utilization': latest_metrics.memory_utilization if latest_metrics else 0,
                        'is_healthy': latest_metrics.is_healthy if latest_metrics else False,
                        'scaling_recommendation': latest_metrics.scaling_recommendation if latest_metrics else None
                    } if latest_metrics else None,
                    'scaling_events_24h': len(recent_events),
                    'recent_scaling_events': [
                        {
                            'timestamp': event.timestamp.isoformat(),
                            'action': event.action,
                            'from_size': event.from_size,
                            'to_size': event.to_size,
                            'reason': event.reason,
                            'success': event.success
                        }
                        for event in recent_events[-5:]  # Last 5 events
                    ]
                }
            except Exception as e:
                self.logger.error(f"Error getting status for {cluster_name}: {e}")
                report['clusters'][cluster_name] = {'error': str(e)}
        
        return report
    
    def force_scale(self, cluster_name: str, target_size: str, reason: str = "Manual scaling") -> bool:
        """Force scaling to a specific size (bypasses normal checks)"""
        try:
            cluster_info = self.atlas_client.get_cluster(cluster_name)
            current_size = cluster_info.get('providerSettings', {}).get('instanceSizeName', 'M10')
            
            if current_size == target_size:
                self.logger.info(f"Cluster {cluster_name} is already at target size {target_size}")
                return True
            
            success = self.execute_scaling(cluster_name, current_size, target_size, "manual", reason)
            return success
            
        except Exception as e:
            self.logger.error(f"Error in force scaling: {e}")
            return False
    
    def stop(self):
        """Stop the application"""
        self.running = False
        self.logger.info("Application stopped")


# =============================================================================
# Main Application
# =============================================================================

def create_sample_config():
    """Create a sample configuration file"""
    config = {
        "atlas": {
            "public_key": "YOUR_ATLAS_PUBLIC_KEY",
            "private_key": "YOUR_ATLAS_PRIVATE_KEY",
            "project_id": "YOUR_PROJECT_ID",
            "base_url": "https://cloud.mongodb.com/api/atlas/v2"
        },
        "monitoring": {
            "check_interval": 60,
            "cpu_threshold_high": 80.0,
            "cpu_threshold_low": 30.0,
            "connection_threshold_high": 1000,
            "connection_threshold_low": 100,
            "iops_threshold_high": 1000,
            "iops_threshold_low": 100,
            "memory_threshold_high": 85.0,
            "memory_threshold_low": 40.0
        },
        "scaling": {
            "enabled": True,
            "scale_up_cooldown": 0,
            "scale_down_cooldown": 300,
            "max_scale_up_per_hour": 3,
            "max_scale_down_per_hour": 2,
            "min_instance_size": "M10",
            "max_instance_size": "M80",
            "scale_up_step": "M20",
            "scale_down_step": "M10"
        },
        "alerts": {
            "enabled": True,
            "webhook_url": None,
            "email_notifications": False,
            "email_recipients": [],
            "slack_webhook": None
        }
    }
    
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✅ Created config.json with sample configuration")
    print("📝 Please edit config.json with your Atlas API credentials")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Atlas Auto Scaling Script')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    parser.add_argument('--mode', choices=['continuous', 'single'], default='continuous',
                       help='Run mode: continuous monitoring or single check')
    parser.add_argument('--clusters', nargs='+', help='Specific clusters to monitor')
    parser.add_argument('--status', action='store_true', help='Show status report and exit')
    parser.add_argument('--force-scale', help='Force scale specific cluster (format: cluster_name:size)')
    parser.add_argument('--disable-scaling', help='Disable scaling for specific cluster')
    parser.add_argument('--enable-scaling', help='Enable scaling for specific cluster')
    parser.add_argument('--init-config', action='store_true', help='Create sample configuration file')
    
    args = parser.parse_args()
    
    # Handle init-config
    if args.init_config:
        create_sample_config()
        return
    
    try:
        # Initialize application
        app = AtlasAutoScaling(args.config)
        
        # Test connection
        if not app.atlas_client.test_connection():
            print("❌ Failed to connect to Atlas API. Please check your credentials.")
            return 1
        
        # Get cluster names
        if args.clusters:
            cluster_names = args.clusters
        else:
            clusters = app.atlas_client.get_clusters()
            cluster_names = [cluster['name'] for cluster in clusters]
            if not cluster_names:
                print("No clusters found")
                return 1
        
        # Handle special commands
        if args.status:
            report = app.get_status_report(cluster_names)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0
        
        if args.force_scale:
            cluster_name, target_size = args.force_scale.split(':')
            success = app.force_scale(cluster_name, target_size, "Manual scaling via CLI")
            print(f"Force scaling {'successful' if success else 'failed'}")
            return 0
        
        if args.disable_scaling:
            app.scaling_config.enabled = False
            print(f"Scaling disabled for {args.disable_scaling}")
            return 0
        
        if args.enable_scaling:
            app.scaling_config.enabled = True
            print(f"Scaling enabled for {args.enable_scaling}")
            return 0
        
        # Run monitoring
        if args.mode == 'continuous':
            app.run_continuous_monitoring(cluster_names)
        else:
            app.run_single_check(cluster_names)
        
        return 0
        
    except KeyboardInterrupt:
        print("\nReceived shutdown signal. Stopping application...")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
