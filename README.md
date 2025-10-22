# Atlas Auto Scaling Script

A comprehensive auto-scaling solution for MongoDB Atlas clusters in a single Python file, based on [MongoDB Atlas Scheduled Triggers](https://www.mongodb.com/developer/products/atlas/atlas-cluster-automation-using-scheduled-triggers/) approach and using [Atlas Admin API v2](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/). Provides high-frequency monitoring, real-time scaling decisions, and flexible configuration options.

## 🚀 Key Features

### Core Capabilities
- **High-Frequency Monitoring**: Support for minute-level monitoring of critical performance metrics
- **Zero-Delay Scaling**: Configurable 0-delay real-time scaling response
- **Intelligent Decision Making**: Smart scaling decisions based on multi-dimensional metrics (CPU, connections, IOPS, memory)
- **Flexible Configuration**: Fully customizable monitoring thresholds and scaling policies
- **Multi-Channel Alerts**: Support for Webhook, Email, Slack, and other alerting methods
- **Atlas API v2 Support**: Uses the latest Atlas Admin API v2 with proper authentication and endpoints

### Problem Solving
- **Cascade Effect Prevention**: Prevent node resource exhaustion due to traffic spikes
- **Atlas Built-in Limitations**: Overcome the 10-minute delay limitation of Atlas built-in auto-scaling
- **Business Flexibility**: Provide best practice configurations for customer business scenarios

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Configuration │    │   Monitoring    │    │   Scaling       │
│   Manager       │    │   Module        │    │   Engine        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Atlas API     │
                    │   Client        │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   MongoDB       │
                    │   Atlas         │
                    └─────────────────┘
```

### Core Modules

1. **Configuration Management (config.py)**
   - Centralized management of all configuration parameters
   - Support for environment variables and configuration files
   - Configuration validation and error handling

2. **Atlas API Client (atlas_client.py)**
   - Complete Atlas Admin API wrapper
   - Authentication and signature handling
   - Metrics data collection

3. **Monitoring Module (monitor.py)**
   - Real-time metrics collection and processing
   - Health status assessment
   - Trend analysis and alert generation

4. **Scaling Engine (scaler.py)**
   - Intelligent scaling decisions
   - Cooldown period management
   - Scaling history tracking

5. **Alert Management (alerts.py)**
   - Multi-channel alert delivery
   - Alert templates and formatting
   - Alert history management

## 📋 Installation and Configuration

### Requirements
- Python 3.8+
- MongoDB Atlas project and API keys
- Network connectivity to Atlas API

### Installation Steps

1. **Download the Script**
```bash
# Download the single Python file
wget https://raw.githubusercontent.com/yourcompany/atlas-auto-scaling/main/atlas_auto_scaling.py
```

2. **Install Dependencies**
```bash
pip install requests
```

3. **Create Configuration**
```bash
python atlas_auto_scaling.py --init-config
# Edit config.json with your Atlas API credentials
```

4. **Set Environment Variables (Optional)**
```bash
export ATLAS_PUBLIC_KEY="your_public_key"
export ATLAS_PRIVATE_KEY="your_private_key"
export ATLAS_PROJECT_ID="your_project_id"
```

### Configuration Guide

#### Monitoring Configuration
```json
{
  "monitoring": {
    "check_interval": 60,           // Check interval (seconds)
    "cpu_threshold_high": 80.0,     // CPU high threshold (%)
    "cpu_threshold_low": 30.0,      // CPU low threshold (%)
    "connection_threshold_high": 1000,  // Connection high threshold
    "connection_threshold_low": 100,     // Connection low threshold
    "iops_threshold_high": 1000,    // IOPS high threshold
    "iops_threshold_low": 100,       // IOPS low threshold
    "memory_threshold_high": 85.0,   // Memory high threshold (%)
    "memory_threshold_low": 40.0     // Memory low threshold (%)
  }
}
```

#### Scaling Configuration
```json
{
  "scaling": {
    "enabled": true,                // Enable auto-scaling
    "scale_up_cooldown": 0,         // Scale-up cooldown (seconds, 0=no delay)
    "scale_down_cooldown": 300,     // Scale-down cooldown (seconds)
    "max_scale_up_per_hour": 3,     // Maximum scale-ups per hour
    "max_scale_down_per_hour": 2,   // Maximum scale-downs per hour
    "min_instance_size": "M10",      // Minimum instance size
    "max_instance_size": "M80",     // Maximum instance size
    "scale_up_step": "M20",         // Scale-up step size
    "scale_down_step": "M10"        // Scale-down step size
  }
}
```

## 🚀 Usage

### Basic Usage

1. **Continuous Monitoring Mode**
```bash
python atlas_auto_scaling.py --mode continuous
```

2. **Single Check Mode**
```bash
python atlas_auto_scaling.py --mode single
```

3. **Monitor Specific Clusters**
```bash
python atlas_auto_scaling.py --clusters cluster1 cluster2
```

### Advanced Features

1. **View Status Report**
```bash
python atlas_auto_scaling.py --status
```

2. **Force Scaling**
```bash
python atlas_auto_scaling.py --force-scale cluster1:M40
```

3. **Disable/Enable Scaling**
```bash
python atlas_auto_scaling.py --disable-scaling cluster1
python atlas_auto_scaling.py --enable-scaling cluster1
```

### Best Practice Configurations

#### High Traffic Scenario
```json
{
  "monitoring": {
    "check_interval": 30,           // More frequent checks
    "cpu_threshold_high": 70.0,     // More sensitive CPU threshold
    "scale_up_cooldown": 0          // Zero-delay scaling
  },
  "scaling": {
    "max_scale_up_per_hour": 5,     // Allow more frequent scaling
    "scale_up_step": "M30"          // Larger scaling step
  }
}
```

#### Cost Optimization Scenario
```json
{
  "monitoring": {
    "cpu_threshold_low": 20.0,      // More aggressive scale-down
    "scale_down_cooldown": 600     // Longer scale-down cooldown
  },
  "scaling": {
    "max_scale_down_per_hour": 1    // Limit scale-down frequency
  }
}
```

## 📊 Monitoring Metrics

### Supported Metrics
- **CPU Utilization**: Processor usage percentage
- **Connection Count**: Current database connections
- **IOPS**: Input/Output operations per second
- **Memory Utilization**: Memory usage percentage

### Metrics Collection Frequency
- Default: Once per minute
- Configurable: 10 seconds to 1 hour
- Historical Data: Retains last 100 data points

## 🔧 Troubleshooting

### Common Issues

1. **API Connection Failure**
   - Check Atlas API credentials
   - Verify network connectivity
   - Validate project ID

2. **Scaling Failures**
   - Check cluster status
   - Verify instance size limits
   - Review cooldown settings

3. **Alerts Not Sent**
   - Check alert configuration
   - Verify webhook URLs
   - Confirm SMTP settings

### Log Analysis
```bash
# View application logs
tail -f atlas_scaling.log

# View error logs
grep ERROR atlas_scaling.log
```

## 🔒 Security Considerations

### API Security
- Use environment variables for sensitive credentials
- Regularly rotate API keys
- Limit API permission scope

### Network Security
- Use HTTPS connections
- Configure firewall rules
- Monitor for unusual API calls

## 📈 Performance Optimization

### Monitoring Optimization
- Adjust check intervals to balance performance and cost
- Use metric aggregation to reduce API calls
- Implement exponential backoff retry mechanisms

### Scaling Optimization
- Configure appropriate cooldown periods
- Use predictive scaling
- Implement gradual scaling strategies

## 🤝 Contributing

### Development Environment Setup
```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest black flake8 mypy

# Run tests
pytest

# Code formatting
black .

# Code linting
flake8 .
mypy .
```

### Submission Guidelines
- Use clear commit messages
- Include test cases
- Update documentation

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 📞 Support

- Issue Reporting: [GitHub Issues](https://github.com/yourcompany/atlas-auto-scaling/issues)
- Documentation: [Project Wiki](https://github.com/yourcompany/atlas-auto-scaling/wiki)
- Contact: [kevin.kotsunleung@gmail.com](mailto:kevin.kotsunleung@gmail.com)

---

**Note**: This script is a custom solution. Please adjust configuration parameters according to your specific needs. Thorough testing is recommended before production use.
