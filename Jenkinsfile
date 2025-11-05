pipeline {
    agent any

    environment {
        DOCKER_USER = 'usmanfarooq317'
        IMAGE_NAME = 'ret-api-dashboard'
    }

    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/usmanfarooq317/ret-apis.git'
            }
        }

        stage('Generate Version Tag') {
            steps {
                script {
                    // Get list of Docker Hub image tags
                    def existingTags = sh(
                        script: "curl -s https://hub.docker.com/v2/repositories/${DOCKER_USER}/${IMAGE_NAME}/tags/?page_size=100 | jq -r '.results[].name'",
                        returnStdout: true
                    ).trim().split('\n')

                    // Filter tags like 'v1', 'v2', and find max
                    def versionTags = existingTags.findAll { it ==~ /v[0-9]+/ }
                    def latestVersion = versionTags.collect { it.replace('v', '').toInteger() }.max() ?: 0
                    env.NEW_VERSION = "v${latestVersion + 1}"

                    echo "✅ New Version will be: ${env.NEW_VERSION}"
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh """
                docker build -t ${DOCKER_USER}/${IMAGE_NAME}:latest \
                             -t ${DOCKER_USER}/${IMAGE_NAME}:${env.NEW_VERSION} .
                """
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-credentials', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
                    sh """
                    echo $DOCKER_PASS | docker login -u $DOCKER_USER --password-stdin
                    docker push ${DOCKER_USER}/${IMAGE_NAME}:latest
                    docker push ${DOCKER_USER}/${IMAGE_NAME}:${env.NEW_VERSION}
                    """
                }
            }
        }

        stage('Deploy to EC2') {
            steps {
                sshagent(['ec2-ssh-key']) {
                    sh """
                    ssh -o StrictHostKeyChecking=no ubuntu@54.89.241.89 '
                        docker pull ${DOCKER_USER}/${IMAGE_NAME}:${env.NEW_VERSION} &&
                        docker stop ret-api || true &&
                        docker rm ret-api || true &&
                        docker run -d --name ret-api -p 5000:5000 ${DOCKER_USER}/${IMAGE_NAME}:${env.NEW_VERSION}
                    '
                    """
                }
            }
        }
    }

    post {
        success {
            echo "✅ Build & Deployment Successful! Version: ${env.NEW_VERSION}"
        }
        failure {
            echo "❌ Build Failed! Version not updated."
        }
    }
}
