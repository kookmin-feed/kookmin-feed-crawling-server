# Scraper Lambda Production/Development Environment Separation Documentation

## Overview
This document summarizes the comprehensive discussion and implementation of separating a scraper lambda system into production (prod) and development (dev) environments. The separation was implemented to improve development workflow, testing procedures, and deployment management.

## Key Participants
- **김종민** (Project Lead/Developer)
- **이현구** (Technical Consultant/Reviewer)

## Timeline
**Date**: August 29, 2025  
**Duration**: Approximately 11 hours (5:04 AM - 4:50 PM)

## Initial Situation
- Existing scraper lambda system was running in a single environment
- Need for proper separation between production and development environments
- Requirement to implement proper deployment workflows and testing procedures

## Implementation Steps

### 1. Environment Cleanup
- **Action**: Complete removal of existing stacks and resources
- **Reason**: Fresh start with proper naming conventions
- **Result**: Clean slate for implementing new architecture

### 2. Naming Convention Implementation
- **Production**: `prod-*` prefix for all resources
- **Development**: `dev-*` prefix for all resources
- **Examples**:
  - `prod-master` vs `dev-master`
  - `prod-architecture_academic_scraper` vs `dev-architecture_academic_scraper`

### 3. Infrastructure as Code Updates
- **CloudFormation Stacks**: Separate stacks for prod and dev
- **Lambda Functions**: 95 total functions (45 scrapers + master + others)
- **EventBridge Schedules**: Separate scheduling for prod and dev environments
- **Applications**: Two separate serverless applications

### 4. IAM Policy Configuration
- **Shared Policy**: Both environments use the same IAM policy
- **Wildcard Access**: `arn:aws:lambda:ap-northeast-2:558793517018:function:*`
- **Rationale**: Simplified management while maintaining security

### 5. Database Separation
- **Production Database**: Separate database for production data
- **Development Database**: Separate database for development/testing
- **Purpose**: Isolate data between environments

### 6. GitHub Actions Workflow
- **Trigger Branches**: `dev` and `prod`
- **Dynamic Deployment**: Stage automatically determined by branch name
- **Concurrency Control**: Prevents duplicate deployments

### 7. Repository Secrets Management
- **Production Secrets**: `PROD_DB_NAME`, `PROD_MONGODB_URI`
- **Development Secrets**: `DB_NAME`, `MONGODB_URI`
- **Shared Secrets**: AWS credentials, Slack tokens

## Technical Architecture

### Resource Distribution
- **Lambda Functions**: 95 total
- **Code Storage**: 67.8MB (0% of 75GB limit)
- **Account Concurrency**: 400 (unreserved)
- **Region**: Asia Pacific (Seoul) - ap-northeast-2

### Deployment Flow
1. **Local Development** → **Dev Branch PR** → **Dev Environment Testing**
2. **Dev Environment QA** → **Prod Branch PR** → **Production Deployment**

### Validation Process
- **Scraper Types**: 45 validated scrapers
- **Categories**: 17 scraper categories
- **Function Mapping**: Automatic validation of lambda function existence

## Key Benefits Achieved

### 1. Workflow Improvement
- Clear separation of development and production processes
- Proper testing procedures before production deployment
- Reduced risk of production issues

### 2. Resource Management
- Better resource tracking and monitoring
- Environment-specific configuration management
- Improved debugging and troubleshooting capabilities

### 3. Team Collaboration
- Clear responsibility assignment
- Structured review processes
- Better communication and documentation

## Testing Results

### Development Environment
- **Status**: ✅ Fully functional
- **Scrapers**: 45 scrapers executed successfully
- **Database**: Data properly stored in dev database
- **Scheduling**: Active but can be disabled during normal operations

### Production Environment
- **Status**: ✅ Fully functional after initial issues resolved
- **Scrapers**: 45 scrapers executed successfully
- **Database**: Data properly stored in prod database
- **Scheduling**: Active and running production workloads

## Best Practices Established

### 1. Deployment Process
- No local `sls deploy` commands
- All deployments through GitHub Actions
- Branch-based environment selection

### 2. Testing Strategy
- Local testing → Dev environment testing → Production deployment
- QA validation in dev Discord channel before production
- Clear responsibility and accountability

### 3. Resource Naming
- Consistent prefix-based naming convention
- Easy identification of environment-specific resources
- Simplified management and monitoring

## Future Considerations

### 1. Monitoring and Alerting
- Environment-specific monitoring dashboards
- Separate alerting for prod and dev
- Performance metrics comparison

### 2. Cost Optimization
- Development environment scheduling optimization
- Resource usage monitoring and optimization
- Cost allocation between environments

### 3. Documentation
- Environment-specific runbooks
- Troubleshooting guides
- Deployment procedures

## Conclusion

The successful separation of the scraper lambda system into production and development environments has significantly improved the development workflow, testing procedures, and overall system reliability. The implementation provides a solid foundation for future development and maintenance while maintaining clear separation of concerns between environments.

### Key Success Factors
- Comprehensive planning and execution
- Proper naming conventions and resource organization
- Automated deployment workflows
- Clear testing and validation procedures
- Team collaboration and communication

### Next Steps
- Monitor system performance and stability
- Optimize development environment usage
- Continue improving documentation and procedures
- Consider additional environment-specific optimizations

---

**Document Created**: September 3, 2025  
**Last Updated**: September 3, 2025  
**Status**: Complete