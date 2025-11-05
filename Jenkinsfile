pipeline {
    agent any

    environment {
        DOCKER_USER = 'usmanfarooq317'
        IMAGE_NAME = 'ret-api-dashboard'
    }

    triggers {
        githubPush()   // ✅ Must be inside pipeline block
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
                    def tagsJson = sh(script: "curl -s https://hub.docker.com/v2/repositories/${DOCKER_USER}/${IMAGE_NAME}/tags/?page_size=100 | jq -r '.results[].name' | grep -E '^v[0-9]+' || true", returnStdout: true).trim()

                    if (tagsJson) {
                        def numbers = tagsJson.readLines().collect { it.replace('v', '') as int }
                        env.VERSION = "v" + (numbers.max() + 1)
                    } else {
                        env.VERSION = "v1"
                    }
                    echo "🚀 Generated Version: ${env.VERSION}"
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh """
                docker build -t ${DOCKER_USER}/${IMAGE_NAME}:latest \
                             -t ${DOCKER_USER}/${IMAGE_NAME}:${env.VERSION} .
                """
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-credentials', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
                    sh """
                    echo $PASSWORD | docker login -u $USERNAME --password-stdin
                    docker push ${DOCKER_USER}/${IMAGE_NAME}:latest
                    docker push ${DOCKER_USER}/${IMAGE_NAME}:${env.VERSION}
                    """
                }
            }
        }

        stage('Deploy to EC2') {
            steps {
                sshagent(['ec2-ssh-key']) {
                    sh """
                    ssh -o StrictHostKeyChecking=no ubuntu@54.89.241.89 '
                        docker pull ${DOCKER_USER}/${IMAGE_NAME}:${env.VERSION} &&
                        docker stop ret-api || true &&
                        docker rm ret-api || true &&
                        docker run -d --name ret-api -p 5000:5020 ${DOCKER_USER}/${IMAGE_NAME}:${env.VERSION}
                    '
                    """
                }
            }
        }
    }

    post {
        success {
            echo "✅ Build & Deployment Successful! Version: ${env.VERSION}"
        }
        failure {
            echo "❌ Build Failed! Version not updated."
        }
    }
}
