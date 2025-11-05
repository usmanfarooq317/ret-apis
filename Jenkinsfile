pipeline {
    agent any

    triggers {
        githubPush()
    }

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
                    def existingTags = sh(
                        script: "curl -s https://hub.docker.com/v2/repositories/${DOCKER_USER}/${IMAGE_NAME}/tags/?page_size=100 | jq -r '.results[].name' | grep -E '^v[0-9]+' || true",
                        returnStdout: true
                    ).trim()

                    if (!existingTags) {
                        env.NEW_VERSION = "v1"
                    } else {
                        def numbers = existingTags.readLines().collect { it.replace('v', '').toInteger() }
                        def highest = numbers.max()
                        env.NEW_VERSION = "v" + (highest + 1)
                    }
                    echo "✅ New version to build: ${env.NEW_VERSION}"
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh """
                    docker build -t ${DOCKER_USER}/${IMAGE_NAME}:latest .
                """
            }
        }

        stage('Tag & Push to Docker Hub') {
        when {
            expression { currentBuild.currentResult == null || currentBuild.currentResult == 'SUCCESS' }
        }
        steps {
            script {
                withCredentials([usernamePassword(
                    credentialsId: 'docker-hub',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh """
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        docker tag ${DOCKER_USER}/${IMAGE_NAME}:latest ${DOCKER_USER}/${IMAGE_NAME}:${env.NEW_VERSION}
                        docker push ${DOCKER_USER}/${IMAGE_NAME}:latest
                        docker push ${DOCKER_USER}/${IMAGE_NAME}:${env.NEW_VERSION}
                    """
                }
            }
        }
    }

        stage('Deploy to EC2 (Only on Success)') {
            steps {
                sshagent(['ec2-ssh-key']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ubuntu@54.89.241.89 '
                            docker pull ${DOCKER_USER}/${IMAGE_NAME}:${env.NEW_VERSION} &&
                            docker stop ret-api-dashboard || true &&
                            docker rm ret-api-dashboard || true &&
                            docker run -d --name ret-api-dashboard -p 5000:5020 ${DOCKER_USER}/${IMAGE_NAME}:${env.NEW_VERSION}
                        '
                    """
                }
            }
        }
    }

    post {
        success {
            echo "✅ Build, Tag, Push & Deploy Successful! Version: ${env.NEW_VERSION}"
        }
        failure {
            echo "❌ Build Failed! No tag created, no push, no deploy."
        }
    }
}
