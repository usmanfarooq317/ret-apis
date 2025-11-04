pipeline {
  agent any

  environment {
    DOCKER_IMAGE = "usmanfarooq317/ret-api-dashboard"
    GIT_REPO     = "https://github.com/usmanfarooq317/ret-apis.git"
    EC2_USER     = "ubuntu"
    EC2_HOST     = "54.89.241.89"
    // Credential IDs in Jenkins (create these; see instructions below)
    GITHUB_CRED  = "github-token"
    DOCKER_CRED  = "dockerhub-credentials"
    EC2_KEY_ID   = "ec2-ssh-key"   // MUST be an "SSH Username with private key" credential (username = ubuntu)
  }

  triggers {
    githubPush()
  }

  stages {
    stage('Checkout Code') {
      steps {
        git branch: 'main',
            url: "${GIT_REPO}",
            credentialsId: "${GITHUB_CRED}"
      }
    }

    stage('Determine New Version Tag') {
      steps {
        script {
          // Try to get tags from Docker Hub, fallback to v1 if none
          def tagsJson = sh(
            script: "curl -s https://hub.docker.com/v2/repositories/${DOCKER_IMAGE}/tags/?page_size=100",
            returnStdout: true
          ).trim()

          // Extract all tag names that start with v + digits (no jq required)
          def matcher = (tagsJson =~ /\"name\"\\s*:\\s*\"(v[0-9]+)\"/)
          def nums = []
          for (m in matcher) {
            try {
              nums << (m[1].replaceAll('v','') as Integer)
            } catch (e) { /* ignore parse errors */ }
          }
          if (nums.size() == 0) {
            env.VERSION_TAG = "v1"
          } else {
            nums = nums.sort()
            def next = nums[-1] + 1
            env.VERSION_TAG = "v${next}"
          }
          echo "✅ New version to push: ${env.VERSION_TAG}"
        }
      }
    }

    stage('Cleanup Old Local Images') {
      steps {
        sh """
          docker rmi -f ${DOCKER_IMAGE}:latest || true
          docker rmi -f ${DOCKER_IMAGE}:${VERSION_TAG} || true
        """
      }
    }

    stage('Build Docker Image') {
      steps {
        sh "docker build -t ${DOCKER_IMAGE}:latest ."
      }
    }

    stage('Login & Push Latest to Docker Hub') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${DOCKER_CRED}", usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          sh '''
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
            docker push ${DOCKER_IMAGE}:latest
          '''
        }
      }
    }

    // Tag + push version only if build stage succeeded (this stage will not run on failure)
    stage('Tag & Push Versioned Image (vX)') {
      when { expression { currentBuild.currentResult == null || currentBuild.currentResult == 'SUCCESS' } }
      steps {
        sh """
          docker tag ${DOCKER_IMAGE}:latest ${DOCKER_IMAGE}:${VERSION_TAG}
          docker push ${DOCKER_IMAGE}:${VERSION_TAG}
        """
      }
    }

    stage('Deploy on EC2 (pull & run image)') {
      steps {
        // Use sshUserPrivateKey credential type in Jenkins CI (see credential setup below)
        withCredentials([sshUserPrivateKey(credentialsId: "${EC2_KEY_ID}", keyFileVariable: 'EC2_KEYFILE', usernameVariable: 'EC2_KEY_USER')]) {
          sh """
            # Single-line SSH command avoids heredoc problems and variable mismatches.
            # Ensure the private key path variable ($EC2_KEYFILE) is used, and VERSION_TAG is interpolated here.
            ssh -o StrictHostKeyChecking=no -i "$EC2_KEYFILE" ${EC2_USER}@${EC2_HOST} \\
              "docker pull ${DOCKER_IMAGE}:${VERSION_TAG} && \
               docker stop ret-api-dashboard || true && \
               docker rm ret-api-dashboard || true && \
               docker run -d --name ret-api-dashboard --restart always -p 5020:5020 ${DOCKER_IMAGE}:${VERSION_TAG}"
          """
        }
      }
    }
  } // end stages

  post {
    success {
      echo "✅ Build & Deploy succeeded — version ${VERSION_TAG} pushed and deployed."
    }
    failure {
      echo "❌ Build Failed — version tag not advanced."
    }
  }
}
